from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.api import create_app
from app.config import Settings
from app.models import Cook, Meat, Pellet


def _meat(meat_type: str, pounds: str) -> Meat:
    return Meat(
        type=meat_type,
        pounds=Decimal(pounds),
        price_per_pound=Decimal("2.00"),
        purchased_on=date(2026, 1, 1),
    )


def _cook(
    started_at: datetime,
    meat_id: int,
    *,
    setpoint: float = 275,
    incomplete: bool = False,
    has_gap: bool = False,
    rotisserie: bool = False,
    time_to_done_seconds: int | None = 8_000,
    exclude_from_stats: bool = False,
) -> Cook:
    return Cook(
        started_at=started_at,
        startup_ended_at=started_at + timedelta(minutes=10),
        cook_ended_at=started_at + timedelta(hours=2, minutes=10),
        cooldown_ended_at=started_at + timedelta(hours=2, minutes=40),
        ended_at=started_at + timedelta(hours=2, minutes=40),
        status="closed",
        meat_id=meat_id,
        aggregate_setpoint=setpoint,
        incomplete=incomplete,
        has_gap=has_gap,
        rotisserie=rotisserie,
        time_to_done_seconds=time_to_done_seconds,
        exclude_from_stats=exclude_from_stats,
    )


def _client(sessions: sessionmaker[Session], tmp_path: object) -> TestClient:
    settings = Settings(database_path=":memory:", photo_dir=str(tmp_path))
    return TestClient(create_app(settings=settings, sessions=sessions))


def test_cook_stats_filters_and_summarizes_pork_shoulders(
    sessions: sessionmaker[Session], tmp_path: object
) -> None:
    with sessions() as session:
        shoulder = _meat("Pork Picnic Shoulder", "4.25")
        other = _meat("Beef brisket", "12.00")
        session.add_all([shoulder, other])
        session.flush()
        first = _cook(datetime(2026, 6, 1, 15, tzinfo=UTC), shoulder.id, setpoint=280)
        second = _cook(datetime(2026, 6, 2, 15, tzinfo=UTC), shoulder.id, setpoint=270)
        second.cook_ended_at = second.startup_ended_at + timedelta(hours=3)
        second.cooldown_ended_at = second.cook_ended_at + timedelta(minutes=30)
        second.ended_at = second.cooldown_ended_at
        session.add_all([first, second, _cook(datetime(2026, 6, 3, 15, tzinfo=UTC), other.id)])
        session.commit()

    with _client(sessions, tmp_path) as client:
        response = client.get(
            "/api/stats/cooks?meat_type=picnic&pounds_min=4&pounds_max=5&setpoint=275"
        )

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 2
    assert body["cook_seconds"] == {"avg": 9000, "min": 7200, "max": 10800}
    assert [cook["id"] for cook in body["cooks"]] == [second.id, first.id]
    assert body["cooks"][0]["meat_type"] == "Pork Picnic Shoulder"


def test_excluded_cooks_do_not_affect_any_stats_aggregate(
    sessions: sessionmaker[Session], tmp_path: object
) -> None:
    started = datetime(2026, 6, 1, 15, tzinfo=UTC)
    with sessions() as session:
        meat = _meat("Pork shoulder", "4.00")
        session.add(meat)
        session.flush()
        included = _cook(started, meat.id)
        excluded = _cook(started + timedelta(days=1), meat.id, exclude_from_stats=True)
        excluded.cook_ended_at = excluded.startup_ended_at + timedelta(hours=10)
        excluded.cooldown_ended_at = excluded.cook_ended_at + timedelta(hours=2)
        excluded.ended_at = excluded.cooldown_ended_at
        session.add_all([included, excluded])
        session.commit()

    with _client(sessions, tmp_path) as client:
        stats = client.get("/api/stats/cooks").json()
        meat_types = client.get("/api/stats/meat-types").json()

    assert stats["count"] == 1
    assert stats["cook_seconds"] == {"avg": 7200, "min": 7200, "max": 7200}
    assert stats["grill_seconds"] == {"avg": 9600, "min": 9600, "max": 9600}
    assert stats["startup_seconds"] == {"avg": 600, "min": 600, "max": 600}
    assert stats["cooldown_seconds"] == {"avg": 1800, "min": 1800, "max": 1800}
    assert stats["time_to_done_seconds"] == {"avg": 8000, "min": 8000, "max": 8000}
    assert [cook["id"] for cook in stats["cooks"]] == [included.id]
    assert meat_types == [{"meat_type": "Pork shoulder", "count": 1}]


def test_cook_stats_exclusions_empty_values_and_effective_setpoint(
    sessions: sessionmaker[Session], tmp_path: object
) -> None:
    started = datetime(2026, 6, 1, 15, tzinfo=UTC)
    with sessions() as session:
        meat = _meat("Pork shoulder", "4.00")
        session.add(meat)
        session.flush()
        incomplete = _cook(started, meat.id, incomplete=True)
        gap = _cook(started + timedelta(days=1), meat.id, setpoint=300, has_gap=True)
        override = _cook(
            started + timedelta(days=2), meat.id, setpoint=225, time_to_done_seconds=None
        )
        override.setpoint_override = 275
        session.add_all([incomplete, gap, override])
        session.commit()

    with _client(sessions, tmp_path) as client:
        default = client.get("/api/stats/cooks").json()
        without_gaps = client.get("/api/stats/cooks?exclude_gaps=true").json()
        with_incomplete = client.get("/api/stats/cooks?include_incomplete=true").json()
        overridden = client.get("/api/stats/cooks?setpoint=275&setpoint_tolerance=0").json()
        empty = client.get("/api/stats/cooks?meat_type=chicken").json()

    assert default["count"] == 2
    assert without_gaps["count"] == 1
    assert with_incomplete["count"] == 3
    assert overridden["count"] == 1
    assert overridden["cooks"][0]["setpoint"] == 275
    assert empty["count"] == 0
    assert empty["cook_seconds"] == {"avg": None, "min": None, "max": None}
    assert empty["time_to_done_seconds"] == {"avg": None, "min": None, "max": None}


def test_cook_stats_date_filters_use_los_angeles_dates(
    sessions: sessionmaker[Session], tmp_path: object
) -> None:
    with sessions() as session:
        meat = _meat("Pork shoulder", "4.00")
        session.add(meat)
        session.flush()
        before_midnight = _cook(datetime(2026, 1, 2, 7, 59, tzinfo=UTC), meat.id)
        after_midnight = _cook(datetime(2026, 1, 2, 8, 1, tzinfo=UTC), meat.id)
        session.add_all([before_midnight, after_midnight])
        session.commit()

    with _client(sessions, tmp_path) as client:
        jan_first = client.get("/api/stats/cooks?since=2026-01-01&until=2026-01-01").json()
        jan_second = client.get("/api/stats/cooks?since=2026-01-02&until=2026-01-02").json()

    assert [cook["id"] for cook in jan_first["cooks"]] == [before_midnight.id]
    assert [cook["id"] for cook in jan_second["cooks"]] == [after_midnight.id]


def test_cook_stats_filters_by_pellet_id_and_legacy_pellet_names(
    sessions: sessionmaker[Session], tmp_path: object
) -> None:
    with sessions() as session:
        meat = _meat("Pork shoulder", "4.00")
        hickory = Pellet(
            vendor="Bear Mountain",
            product_name="Hickory",
            price_per_pound=Decimal("1.25"),
            purchased_on=date(2026, 1, 1),
        )
        competition = Pellet(
            vendor="Lumber Jack",
            product_name="Competition Blend",
            price_per_pound=Decimal("1.50"),
            purchased_on=date(2026, 1, 2),
        )
        session.add_all([meat, hickory, competition])
        session.flush()
        first = _cook(datetime(2026, 6, 1, 15, tzinfo=UTC), meat.id)
        first.pellet_id = hickory.id
        second = _cook(datetime(2026, 6, 2, 15, tzinfo=UTC), meat.id)
        second.pellet_id = competition.id
        session.add_all([first, second])
        session.commit()

    with _client(sessions, tmp_path) as client:
        by_id = client.get(f"/api/stats/cooks?pellet_id={hickory.id}").json()
        unknown = client.get("/api/stats/cooks?pellet_id=999999").json()
        by_vendor = client.get("/api/stats/cooks?pellet_vendor=bear").json()
        by_product = client.get("/api/stats/cooks?pellet_product=competition").json()

    assert [cook["id"] for cook in by_id["cooks"]] == [first.id]
    assert unknown["count"] == 0
    assert unknown["cook_seconds"] == {"avg": None, "min": None, "max": None}
    assert [cook["id"] for cook in by_vendor["cooks"]] == [first.id]
    assert [cook["id"] for cook in by_product["cooks"]] == [second.id]


def test_meat_types_returns_distinct_types_and_cook_counts(
    sessions: sessionmaker[Session], tmp_path: object
) -> None:
    with sessions() as session:
        pork = _meat("Pork shoulder", "4.00")
        ribs = _meat("Pork ribs", "3.00")
        unused = _meat("Chicken", "5.00")
        session.add_all([pork, ribs, unused])
        session.flush()
        session.add_all(
            [
                _cook(datetime(2026, 1, 1, tzinfo=UTC), pork.id),
                _cook(datetime(2026, 1, 2, tzinfo=UTC), pork.id),
                _cook(datetime(2026, 1, 3, tzinfo=UTC), ribs.id),
            ]
        )
        session.commit()

    with _client(sessions, tmp_path) as client:
        response = client.get("/api/stats/meat-types")

    assert response.status_code == 200
    assert response.json() == [
        {"meat_type": "Pork ribs", "count": 1},
        {"meat_type": "Pork shoulder", "count": 2},
    ]
