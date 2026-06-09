"""
Test search tools route — CRUD operations.
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from uuid import uuid4
from fastapi.testclient import TestClient
from app.main import create_app
from app.database import init_db, SessionLocal
from app.models import SearchToolConfig

app = create_app()
client = TestClient(app)

_created_ids: list[str] = []


def setup_module():
    init_db()


def teardown_module():
    db = SessionLocal()
    try:
        for stid in _created_ids:
            db.query(SearchToolConfig).filter(SearchToolConfig.id == stid).delete()
        db.commit()
    finally:
        db.close()


def _unique_id() -> str:
    return f"st-{uuid4().hex[:8]}"


class TestSearchToolRoutes:
    """API-level tests for search tool routes."""

    def test_list_search_tools(self):
        resp = client.get("/api/v1/search-tools")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_create_search_tool(self):
        stid = _unique_id()
        resp = client.post("/api/v1/search-tools", json={
            "id": stid,
            "name": "Test Search Engine",
            "tool_type": "web_search",
            "is_active": True,
        })
        assert resp.status_code in (200, 201)
        data = resp.json()
        assert data["id"] == stid
        _created_ids.append(stid)

    def test_create_duplicate_tool(self):
        stid = _unique_id()
        client.post("/api/v1/search-tools", json={
            "id": stid, "name": "Dup", "tool_type": "web_search",
        })
        _created_ids.append(stid)
        resp = client.post("/api/v1/search-tools", json={
            "id": stid, "name": "Dup2", "tool_type": "web_search",
        })
        assert resp.status_code == 400

    def test_update_search_tool(self):
        stid = _unique_id()
        client.post("/api/v1/search-tools", json={
            "id": stid, "name": "Before", "tool_type": "web_search",
        })
        _created_ids.append(stid)
        resp = client.put(f"/api/v1/search-tools/{stid}", json={
            "name": "After",
        })
        assert resp.status_code == 200
        assert resp.json()["name"] == "After"

    def test_update_nonexistent_tool(self):
        resp = client.put("/api/v1/search-tools/nonexistent", json={"name": "X"})
        assert resp.status_code == 404

    def test_delete_search_tool(self):
        stid = _unique_id()
        client.post("/api/v1/search-tools", json={
            "id": stid, "name": "ToDelete", "tool_type": "web_search",
        })
        resp = client.delete(f"/api/v1/search-tools/{stid}")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_delete_nonexistent_tool(self):
        resp = client.delete("/api/v1/search-tools/nonexistent")
        assert resp.status_code == 404
