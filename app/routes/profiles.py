from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.deps import get_session
from app.models import Cook, Profile, ProfileStep
from app.schemas import (
    ProfileCreate,
    ProfileListResponse,
    ProfileResponse,
    ProfileStepInput,
    ProfileUpdate,
)

router = APIRouter(prefix="/api/profiles", tags=["profiles"])
SessionDep = Annotated[Session, Depends(get_session)]


def _get_profile(profile_id: int, session: Session) -> Profile:
    profile = session.get(Profile, profile_id)
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Profile not found")
    return profile


def _check_name(name: str, session: Session, profile_id: int | None = None) -> None:
    query = select(Profile.id).where(Profile.name == name)
    if profile_id is not None:
        query = query.where(Profile.id != profile_id)
    if session.scalar(query.limit(1)) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Profile name already exists")


def _replace_steps(profile_id: int, steps: list[ProfileStepInput], session: Session) -> None:
    session.execute(delete(ProfileStep).where(ProfileStep.profile_id == profile_id))
    session.add_all(
        ProfileStep(profile_id=profile_id, position=position, **step.model_dump())
        for position, step in enumerate(steps, start=1)
    )


def _profile_response(profile: Profile, session: Session) -> ProfileResponse:
    steps = list(
        session.scalars(
            select(ProfileStep)
            .where(ProfileStep.profile_id == profile.id)
            .order_by(ProfileStep.position)
        )
    )
    return ProfileResponse(
        id=profile.id,
        name=profile.name,
        keep_warm=profile.keep_warm,
        keep_warm_temp=profile.keep_warm_temp,
        steps=steps,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


@router.get("", response_model=list[ProfileListResponse])
def list_profiles(session: SessionDep) -> list[ProfileListResponse]:
    rows = session.execute(
        select(Profile, func.count(ProfileStep.id))
        .outerjoin(ProfileStep, ProfileStep.profile_id == Profile.id)
        .group_by(Profile.id)
        .order_by(Profile.name, Profile.id)
    )
    return [
        ProfileListResponse(
            id=profile.id,
            name=profile.name,
            keep_warm=profile.keep_warm,
            keep_warm_temp=profile.keep_warm_temp,
            step_count=step_count,
            created_at=profile.created_at,
            updated_at=profile.updated_at,
        )
        for profile, step_count in rows
    ]


@router.post("", response_model=ProfileResponse, status_code=status.HTTP_201_CREATED)
def create_profile(payload: ProfileCreate, session: SessionDep) -> ProfileResponse:
    _check_name(payload.name, session)
    profile = Profile(**payload.model_dump(exclude={"steps"}))
    session.add(profile)
    session.flush()
    _replace_steps(profile.id, payload.steps, session)
    session.commit()
    session.refresh(profile)
    return _profile_response(profile, session)


@router.get("/{profile_id}", response_model=ProfileResponse)
def get_profile(profile_id: int, session: SessionDep) -> ProfileResponse:
    return _profile_response(_get_profile(profile_id, session), session)


@router.put("/{profile_id}", response_model=ProfileResponse)
def replace_profile(
    profile_id: int, payload: ProfileCreate, session: SessionDep
) -> ProfileResponse:
    profile = _get_profile(profile_id, session)
    _check_name(payload.name, session, profile_id)
    for field, value in payload.model_dump(exclude={"steps"}).items():
        setattr(profile, field, value)
    _replace_steps(profile.id, payload.steps, session)
    session.commit()
    session.refresh(profile)
    return _profile_response(profile, session)


@router.patch("/{profile_id}", response_model=ProfileResponse)
def update_profile(
    profile_id: int, payload: ProfileUpdate, session: SessionDep
) -> ProfileResponse:
    profile = _get_profile(profile_id, session)
    changes = payload.model_dump(exclude_unset=True)
    if "name" in changes:
        _check_name(changes["name"], session, profile_id)

    keep_warm = changes.get("keep_warm", profile.keep_warm)
    keep_warm_temp = changes.get("keep_warm_temp", profile.keep_warm_temp)
    if keep_warm and keep_warm_temp is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "keep_warm_temp is required when keep_warm is true",
        )
    if not keep_warm:
        if "keep_warm_temp" in changes and keep_warm_temp is not None:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "keep_warm_temp must be null when keep_warm is false",
            )
        changes["keep_warm_temp"] = None

    for field, value in changes.items():
        setattr(profile, field, value)
    session.commit()
    session.refresh(profile)
    return _profile_response(profile, session)


@router.delete("/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_profile(profile_id: int, session: SessionDep) -> Response:
    profile = _get_profile(profile_id, session)
    session.execute(update(Cook).where(Cook.profile_id == profile_id).values(profile_id=None))
    session.execute(delete(ProfileStep).where(ProfileStep.profile_id == profile_id))
    session.delete(profile)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
