"""
Test schedules route — CRUD operations.
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from uuid import uuid4
from fastapi.testclient import TestClient
from app.main import create_app
from app.database import init_db, SessionLocal
from app.models import ScheduleConfig

app = create_app()
client = TestClient(app)

_created_ids: list[str] = []


def setup_module():
    init_db()


def teardown_module():
    db = SessionLocal()
    try:
        for sid in _created_ids:
            db.query(ScheduleConfig).filter(ScheduleConfig.id == sid).delete()
        db.commit()
    finally:
        db.close()


def _unique_id() -> str:
    return f"sch-{uuid4().hex[:8]}"


class TestScheduleRoutes:
    """API-level tests for schedule routes."""

    def test_list_schedules(self):
        resp = client.get("/api/v1/schedules")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_create_schedule(self):
        sid = _unique_id()
        resp = client.post("/api/v1/schedules", json={
            "id": sid,
            "name": "Test Schedule",
            "cron_expression": "0 8 * * *",
            "source_ids": ["tavily"],
            "topic_ids": [],
            "is_active": True,
        })
        assert resp.status_code in (200, 201)
        data = resp.json()
        assert data["id"] == sid
        _created_ids.append(sid)

    def test_create_duplicate_schedule(self):
        sid = _unique_id()
        client.post("/api/v1/schedules", json={
            "id": sid, "name": "Dup Schedule",
            "cron_expression": "0 9 * * *",
            "source_ids": ["tavily"], "topic_ids": [],
        })
        _created_ids.append(sid)
        resp = client.post("/api/v1/schedules", json={
            "id": sid, "name": "Dup Schedule 2",
            "cron_expression": "0 10 * * *",
            "source_ids": ["tavily"], "topic_ids": [],
        })
        assert resp.status_code == 400

    def test_delete_schedule(self):
        sid = _unique_id()
        client.post("/api/v1/schedules", json={
            "id": sid, "name": "Delete Me",
            "cron_expression": "0 8 * * *",
            "source_ids": ["tavily"], "topic_ids": [],
        })
        resp = client.delete(f"/api/v1/schedules/{sid}")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_delete_nonexistent_schedule(self):
        resp = client.delete("/api/v1/schedules/nonexistent")
        assert resp.status_code == 404

    def test_run_schedule_now_nonexistent(self):
        resp = client.post("/api/v1/schedules/nonexistent/run-now")
        assert resp.status_code in (400, 404, 500)
