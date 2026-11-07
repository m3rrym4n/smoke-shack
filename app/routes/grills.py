from __future__ import annotations

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass, field
from time import monotonic
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.orm import Session, selectinload

from app.deps import get_session
from app.grill_identity import GrillIdentity, display_grill_identity
from app.grill_profiles import (
    DeviceEntity,
    GrillProfile,
    resolve_channels,
    resolve_status_entities,
)
from app.ha import HAClient, HARegistrySnapshot
from app.models import Channel, Cook, Equipment, EquipmentEntity

router = APIRouter(prefix="/api/grills", tags=["grills"])
SessionDep = Annotated[Session, Depends(get_session)]
_DISCOVERED_IDENTITY_CACHE_SECONDS = 60.0


@dataclass
class _DiscoveredIdentityCache:
    identities: dict[int, GrillIdentity] | None = None
    expires_at: float = 0.0
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class GrillResponse(BaseModel):
    id: str
    name: str
    maker: str | None
    model: str | None
    profile_id: str | None
    device_status: Literal["available", "not_available"]
    equipment_id: int | None
    photo_url: str | None
    logo_url: str | None
    connection_status: Literal["connected", "disconnected"]


@router.get("")
async def list_grills(request: Request, session: SessionDep) -> list[GrillResponse]:
    snapshot = await _registry_snapshot(request)
    equipment = _equipment(session)
    profiles: tuple[GrillProfile, ...] = request.app.state.grill_profiles
    return _visible_grills(snapshot, profiles, equipment)


async def discovered_equipment_identities(
    request: Request, session: Session
) -> dict[int, GrillIdentity]:
    """Return the device identities Settings displays, keyed by equipment id."""
    if not callable(getattr(request.app.state.ha_client, "registry_snapshot", None)):
        return {}
    cache = _discovered_identity_cache(request)
    if cache.identities is not None and monotonic() < cache.expires_at:
        return cache.identities

    async with cache.lock:
        if cache.identities is not None and monotonic() < cache.expires_at:
            return cache.identities
        try:
            snapshot = await _registry_snapshot(request)
        except HTTPException:
            if cache.identities is not None:
                cache.expires_at = monotonic() + _DISCOVERED_IDENTITY_CACHE_SECONDS
                return cache.identities
            return {}
        profiles: tuple[GrillProfile, ...] = request.app.state.grill_profiles
        cache.identities = {
            grill.equipment_id: GrillIdentity(grill.maker, grill.model)
            for grill in _visible_grills(snapshot, profiles, _equipment(session))
            if grill.equipment_id is not None
        }
        cache.expires_at = monotonic() + _DISCOVERED_IDENTITY_CACHE_SECONDS
        return cache.identities


@router.post("/{grill_id}/connect", response_model=GrillResponse)
async def connect_grill(grill_id: str, request: Request, session: SessionDep) -> GrillResponse:
    _refuse_during_cook(session)
    snapshot = await _registry_snapshot(request)
    profiles: tuple[GrillProfile, ...] = request.app.state.grill_profiles
    grills = _visible_grills(snapshot, profiles, _equipment(session))
    grill = next((item for item in grills if item.id == grill_id), None)
    if grill is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Grill not found")

    device = next(item for item in snapshot.devices if item.get("id") == grill_id)
    profile = _matching_profile(device, profiles)
    device_entities = tuple(
        _device_entity(entity)
        for entity in snapshot.entities
        if entity.get("device_id") == grill_id and isinstance(entity.get("entity_id"), str)
    )
    equipment = session.get(Equipment, grill.equipment_id) if grill.equipment_id else None
    if equipment is None:
        if profile is None:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "Grill has no mapping profile",
            )
        resolution = resolve_channels(profile, device_entities)
        if resolution.missing_roles:
            missing = ", ".join(resolution.missing_roles)
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"Grill is missing mapped channels: {missing}",
            )
        equipment = Equipment(
            nickname=grill.name,
            maker=profile.maker,
            model=profile.model,
            type=profile.type,
            fuel_type=profile.fuel_type,
            units=profile.units,
            connected=False,
            stale_after_seconds=profile.stale_after_seconds,
        )
        equipment.channels = [
            Channel(
                key=channel.key,
                role=channel.role,
                label=channel.label,
                source_entity=channel.source_entity_id,
                target_entity=channel.target_entity_id,
                position=position,
            )
            for position, channel in enumerate(resolution.channels)
        ]
        session.add(equipment)
        session.flush()

    if profile is not None:
        existing_roles = {entity.role for entity in equipment.entities}
        equipment.entities.extend(
            EquipmentEntity(role=entity.role, entity_id=entity.entity_id)
            for entity in resolve_status_entities(profile, device_entities)
            if entity.role not in existing_roles
        )
        if equipment.stale_after_seconds is None:
            equipment.stale_after_seconds = profile.stale_after_seconds

    session.execute(update(Equipment).values(connected=False))
    equipment.connected = True
    session.commit()
    _refresh_watch_list(request)
    _clear_discovered_identity_cache(request)
    grill.equipment_id = equipment.id
    grill.connection_status = "connected"
    return grill


@router.post("/{grill_id}/disconnect", response_model=GrillResponse)
async def disconnect_grill(grill_id: str, request: Request, session: SessionDep) -> GrillResponse:
    _refuse_during_cook(session)
    snapshot = await _registry_snapshot(request)
    profiles: tuple[GrillProfile, ...] = request.app.state.grill_profiles
    grills = _visible_grills(snapshot, profiles, _equipment(session))
    grill = next((item for item in grills if item.id == grill_id), None)
    if grill is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Grill not found")
    if grill.equipment_id is not None:
        equipment = session.get(Equipment, grill.equipment_id)
        if equipment is not None:
            equipment.connected = False
            session.commit()
            _refresh_watch_list(request)
    _clear_discovered_identity_cache(request)
    grill.connection_status = "disconnected"
    return grill


def _refresh_watch_list(request: Request) -> None:
    client = request.app.state.ha_client
    refresh = getattr(client, "refresh_watch_list", None)
    if refresh is not None:
        refresh()


def _discovered_identity_cache(request: Request) -> _DiscoveredIdentityCache:
    cache = getattr(request.app.state, "discovered_identity_cache", None)
    if cache is None:
        cache = _DiscoveredIdentityCache()
        request.app.state.discovered_identity_cache = cache
    return cache


def _clear_discovered_identity_cache(request: Request) -> None:
    cache = _discovered_identity_cache(request)
    cache.identities = None
    cache.expires_at = 0.0


async def _registry_snapshot(request: Request) -> HARegistrySnapshot:
    client: HAClient | None = request.app.state.ha_client
    if client is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Home Assistant is not configured")
    try:
        snapshot = await client.registry_snapshot()
    except (OSError, RuntimeError) as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            f"Home Assistant is unavailable: {exc}",
        ) from exc

    return snapshot


def _equipment(session: Session) -> Sequence[Equipment]:
    return session.scalars(
        select(Equipment).options(selectinload(Equipment.channels)).order_by(Equipment.id)
    ).all()


def _refuse_during_cook(session: Session) -> None:
    active = session.scalar(
        select(Cook.id).where(Cook.ended_at.is_(None), Cook.status != "planned")
    )
    if active is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Cannot change the connected grill while a cook is in progress",
        )


def _device_entity(entity: dict[str, Any]) -> DeviceEntity:
    entity_id = str(entity["entity_id"])
    return DeviceEntity(
        entity_id=entity_id,
        domain=entity_id.partition(".")[0],
        unique_id_suffix=_text(entity.get("unique_id")),
        original_name=_text(entity.get("original_name")),
    )


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
                    channel.source_entity in entity_ids or channel.target_entity in entity_ids
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

        # Registry-only entities are disabled or removed. Of entities with state,
        # HA's "unknown" still means the device is present but has not reported yet.
        main_states = [states[entity_id] for entity_id in main_entities if entity_id in states]
        available = any(state != "unavailable" for state in main_states)
        discovered_identity = GrillIdentity(
            maker=_text(device.get("manufacturer")),
            model=_text(device.get("model")),
        )
        identity = display_grill_identity(matched_equipment, discovered_identity)
        maker = identity.maker
        model = identity.model
        name = _text(device.get("name_by_user")) or _text(device.get("name")) or model or device_id
        results.append(
            GrillResponse(
                id=device_id,
                name=name,
                maker=maker,
                model=model,
                profile_id=profile.id if profile else None,
                device_status="available" if available else "not_available",
                equipment_id=matched_equipment.id if matched_equipment else None,
                photo_url=(
                    f"/api/equipment/{matched_equipment.id}/photo"
                    if matched_equipment is not None and matched_equipment.photo_path is not None
                    else None
                ),
                logo_url=(
                    f"/api/equipment/{matched_equipment.id}/logo"
                    if matched_equipment is not None and matched_equipment.logo_path is not None
                    else None
                ),
                connection_status=(
                    "connected"
                    if matched_equipment is not None and matched_equipment.connected
                    else "disconnected"
                ),
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


def _main_entity_ids(profile: GrillProfile | None, entities: list[dict[str, Any]]) -> set[str]:
    if profile is None:
        return set()
    resolved = resolve_channels(
        profile,
        (_device_entity(entity) for entity in entities),
    )
    return {channel.source_entity_id for channel in resolved.channels}


def _text(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None
