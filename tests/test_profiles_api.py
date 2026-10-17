from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.api import create_app
from app.models import Cook, ProfileStep


def profile_payload(name: str = "Pulled Pork") -> dict[str, object]:
    return {
        "name": name,
        "keep_warm": True,
        "keep_warm_temp": 165,
        "steps": [
            {
                "grill_temp": 380,
                "stop_mode": "time",
                "duration_minutes": 30,
                "instructions": "Start hot",
            },
            {
                "grill_temp": 215,
                "stop_mode": "internal_temp",
                "probe": 1,
                "target_temp": 193,
                "instructions": "",
            },
        ],
    }


def test_create_list_and_get_profile_with_ordered_steps(
    sessions: sessionmaker[Session],
) -> None:
    with TestClient(create_app(sessions=sessions)) as client:
        response = client.post("/api/profiles", json=profile_payload())
        assert response.status_code == 201
        created = response.json()
        assert [step["position"] for step in created["steps"]] == [1, 2]
        assert [step["grill_temp"] for step in created["steps"]] == [380, 215]
        assert created["created_at"].endswith("Z")

        listed = client.get("/api/profiles").json()
        assert listed[0]["step_count"] == 2
        assert "steps" not in listed[0]
        assert client.get(f"/api/profiles/{created['id']}").json() == created


def test_put_replaces_steps_and_patch_changes_only_profile_fields(
    sessions: sessionmaker[Session],
) -> None:
    with TestClient(create_app(sessions=sessions)) as client:
        profile_id = client.post("/api/profiles", json=profile_payload()).json()["id"]
        replacement = {
            "name": "Brisket",
            "keep_warm": False,
            "keep_warm_temp": None,
            "steps": [
                {
                    "grill_temp": 250,
                    "stop_mode": "time",
                    "duration_minutes": 60,
                }
            ],
        }
        replaced = client.put(f"/api/profiles/{profile_id}", json=replacement)
        assert replaced.status_code == 200
        assert replaced.json()["name"] == "Brisket"
        assert len(replaced.json()["steps"]) == 1
        assert replaced.json()["steps"][0]["position"] == 1

        patched = client.patch(
            f"/api/profiles/{profile_id}",
            json={"keep_warm": True, "keep_warm_temp": 170},
        )
        assert patched.status_code == 200
        assert patched.json()["keep_warm_temp"] == 170
        assert len(patched.json()["steps"]) == 1

    with sessions() as session:
        assert len(list(session.scalars(select(ProfileStep)))) == 1


def test_profile_validation_rules(sessions: sessionmaker[Session]) -> None:
    valid = profile_payload()
    invalid_payloads = [
        {**valid, "steps": []},
        {**valid, "steps": [{"grill_temp": 149, "stop_mode": "time", "duration_minutes": 1}]},
        {**valid, "steps": [{"grill_temp": 501, "stop_mode": "time", "duration_minutes": 1}]},
        {**valid, "steps": [{"grill_temp": 225, "stop_mode": "time"}]},
        {
            **valid,
            "steps": [
                {
                    "grill_temp": 225,
                    "stop_mode": "time",
                    "duration_minutes": 10,
                    "probe": 1,
                }
            ],
        },
        {**valid, "steps": [{"grill_temp": 225, "stop_mode": "internal_temp"}]},
        {
            **valid,
            "steps": [
                {
                    "grill_temp": 225,
                    "stop_mode": "internal_temp",
                    "probe": 3,
                    "target_temp": 200,
                }
            ],
        },
        {**valid, "keep_warm": True, "keep_warm_temp": None},
        {**valid, "keep_warm": False, "keep_warm_temp": 165},
    ]
    with TestClient(create_app(sessions=sessions)) as client:
        for payload in invalid_payloads:
            assert client.post("/api/profiles", json=payload).status_code == 422


def test_duplicate_name_returns_409(sessions: sessionmaker[Session]) -> None:
    with TestClient(create_app(sessions=sessions)) as client:
        assert client.post("/api/profiles", json=profile_payload()).status_code == 201
        assert client.post("/api/profiles", json=profile_payload()).status_code == 409


def test_delete_profile_removes_steps_and_clears_cook_reference(
    sessions: sessionmaker[Session],
) -> None:
    with TestClient(create_app(sessions=sessions)) as client:
        profile_id = client.post("/api/profiles", json=profile_payload()).json()["id"]
        with sessions() as session:
            cook = Cook(started_at=datetime(2026, 1, 1, tzinfo=UTC), profile_id=profile_id)
            session.add(cook)
            session.commit()
            cook_id = cook.id

        response = client.delete(f"/api/profiles/{profile_id}")
        assert response.status_code == 204
        assert client.get(f"/api/profiles/{profile_id}").status_code == 404

    with sessions() as session:
        assert session.get(Cook, cook_id).profile_id is None
        assert list(session.scalars(select(ProfileStep))) == []
