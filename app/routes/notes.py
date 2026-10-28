from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import get_session
from app.models import Cook, Note
from app.schemas import NoteCreate, NoteResponse, NoteScope, NoteUpdate

router = APIRouter(prefix="/api/notes", tags=["notes"])
SessionDep = Annotated[Session, Depends(get_session)]


def _get_note(note_id: int, session: Session) -> Note:
    note = session.get(Note, note_id)
    if note is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Note not found")
    return note


def _validate_cook(cook_id: int | None, session: Session) -> None:
    if cook_id is not None and session.get(Cook, cook_id) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Cook not found")


@router.get("", response_model=list[NoteResponse])
def list_notes(
    session: SessionDep,
    scope: Annotated[NoteScope | None, Query()] = None,
    cook_id: int | None = None,
) -> list[Note]:
    query = select(Note)
    if scope is not None:
        query = query.where(Note.scope == scope)
    if cook_id is not None:
        query = query.where(Note.cook_id == cook_id)
    return list(session.scalars(query.order_by(Note.created_at.desc(), Note.id.desc())))


@router.post("", response_model=NoteResponse, status_code=status.HTTP_201_CREATED)
def create_note(payload: NoteCreate, session: SessionDep) -> Note:
    _validate_cook(payload.cook_id, session)
    note = Note(**payload.model_dump())
    session.add(note)
    session.commit()
    session.refresh(note)
    return note


@router.get("/{note_id}", response_model=NoteResponse)
def get_note(note_id: int, session: SessionDep) -> Note:
    return _get_note(note_id, session)


@router.patch("/{note_id}", response_model=NoteResponse)
def update_note(note_id: int, payload: NoteUpdate, session: SessionDep) -> Note:
    note = _get_note(note_id, session)
    changes = payload.model_dump(exclude_unset=True)
    if "cook_id" in changes:
        _validate_cook(changes["cook_id"], session)
    for field, value in changes.items():
        setattr(note, field, value)
    session.commit()
    session.refresh(note)
    return note


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_note(note_id: int, session: SessionDep) -> Response:
    session.delete(_get_note(note_id, session))
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
