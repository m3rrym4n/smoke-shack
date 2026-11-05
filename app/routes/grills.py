from __future__ import annotations

from collections.abc import Sequence
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.deps import get_session
from app.grill_profiles import DeviceEntity, GrillProfile, resolve_channels
from app.ha import HAClient, HARegistrySnapshot
from app.models import Equipment

router = APIRouter(prefix="/api/grills", tags=["grills"])
SessionDep = Annotated[Session, Depends(get_session)]


class GrillResponse(BaseModel):
    id: str
    name: str
    maker: str | None
    model: str | None
    profile_id: str | None
    device_status: Literal["available", "not_available"]
    equipment_id: int | None


@router.get("")
async def list_grills(request: Request, session: SessionDep) -> list[GrillResponse]:
    client: HAClient | None = request.app.state.ha_client
    if client is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Home Assistant is not configured"
        )
    try:
        snapshot = await client.registry_snapshot()
    except (OSError, RuntimeError) as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            f"Home Assistant is unavailable: {exc}",
        ) from exc

    equipment = session.scalars(
        select(Equipment).options(selectinload(Equipment.channels)).order_by(Equipment.id)
    ).all()
    profiles: tuple[GrillProfile, ...] = request.app.state.grill_profiles
    return _visible_grills(snapshot, profiles, equipment)


def _visible_grills(
    snapshot: HARegistrySnapshot,
    profiles: tuple[GrillProfile, ...],
    equipment: Sequence[Equipment],
) -> list[GrillResponse]:
    states = {
        item["entity_id"]: item.get("state")
        for item in snapshot.states
        if isinstance(item.get("entity_id"), str)
    }
    entities_by_device: dict[str, list[dict[str, Any]]] = {}
    for entity in snapshot.entities:
        device_id = entity.get("device_id")
        entity_id = entity.get("entity_id")
        if isinstance(device_id, str) and isinstance(entity_id, str):
            entities_by_device.setdefault(device_id, []).append(entity)

    results: list[GrillResponse] = []
    for device in snapshot.devices:
        device_id = device.get("id")
        if not isinstance(device_id, str):
            continue
        device_entities = entities_by_device.get(device_id, [])
        entity_ids = {entity["entity_id"] for entity in device_entities}
        profile = _matching_profile(device, profiles)
        matched_equipment = next(
            (
                item
                for item in equipment
                if any(
                    channel.source_entity in entity_ids
                    or channel.target_entity in entity_ids
                    for channel in item.channels
                )
            ),
            None,
        )
        if profile is None and matched_equipment is None:
            continue

        main_entities = _main_entity_ids(profile, device_entities)
        if matched_equipment is not None:
            main_entities.update(
                channel.source_entity
                for channel in matched_equipment.channels
                if channel.source_entity in entity_ids
            )
        if not main_entities:
            main_entities = entity_ids

        # HA's "unknown" means the present device has not reported yet, so only an
        # explicit unavailable state on every main channel makes it unavailable.
        available = not main_entities or any(
            states.get(entity_id) != "unavailable" for entity_id in main_entities
        )
        maker = _text(device.get("manufacturer"))
        model = _text(device.get("model"))
        name = (
            _text(device.get("name_by_user"))
            or _text(device.get("name"))
            or model
            or device_id
        )
        results.append(
            GrillResponse(
                id=device_id,
                name=name,
                maker=maker,
                model=model,
                profile_id=profile.id if profile else None,
                device_status="available" if available else "not_available",
                equipment_id=matched_equipment.id if matched_equipment else None,
            )
        )
    return results


def _matching_profile(
    device: dict[str, Any], profiles: tuple[GrillProfile, ...]
) -> GrillProfile | None:
    manufacturer = _text(device.get("manufacturer"))
    model = _text(device.get("model"))
    return next(
        (
            profile
            for profile in profiles
            if manufacturer == profile.device_match.manufacturer
            and model == profile.device_match.model
        ),
        None,
    )


def _main_entity_ids(
    profile: GrillProfile | None, entities: list[dict[str, Any]]
) -> set[str]:
    if profile is None:
        return set()
    resolved = resolve_channels(
        profile,
        (
            DeviceEntity(
                entity_id=entity["entity_id"],
                domain=entity["entity_id"].partition(".")[0],
                unique_id_suffix=_text(entity.get("unique_id")),
                original_name=_text(entity.get("original_name")),
            )
            for entity in entities
        ),
    )
    return {channel.source_entity_id for channel in resolved.channels}


def _text(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None
