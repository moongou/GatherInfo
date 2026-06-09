"""
Test source service layer using real database.
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from uuid import uuid4
from fastapi.testclient import TestClient
from fastapi import HTTPException
from app.main import create_app
from app.database import init_db, SessionLocal
from app.models import SourceConfig

app = create_app()
client = TestClient(app)

_created_ids: list[str] = []


def setup_module():
    init_db()


def teardown_module():
    db = SessionLocal()
    try:
        for sid in _created_ids:
            db.query(SourceConfig).filter(SourceConfig.id == sid).delete()
        db.commit()
    finally:
        db.close()


def _unique_id(prefix: str = "test-src") -> str:
    return f"{prefix}-{uuid4().hex[:8]}"


class TestSourceServiceCRUD:
    """Test source_service CRUD functions."""

    def test_create_source(self):
        from app.services.source_service import create_source
        sid = _unique_id()
        db = SessionLocal()
        try:
            src = create_source(db, {"id": sid, "name": "Test Create", "channel": "rss"})
            _created_ids.append(sid)
            assert src.id == sid
            assert src.name == "Test Create"
            assert src.channel == "rss"
        finally:
            db.close()

    def test_create_source_duplicate(self):
        from app.services.source_service import create_source
        sid = _unique_id()
        db = SessionLocal()
        try:
            create_source(db, {"id": sid, "name": "Dup", "channel": "rss"})
            _created_ids.append(sid)
            try:
                create_source(db, {"id": sid, "name": "Dup2", "channel": "rss"})
                assert False, "Expected HTTPException"
            except HTTPException as e:
                assert e.status_code == 400
        finally:
            db.close()

    def test_create_source_auto_id(self):
        from app.services.source_service import create_source
        db = SessionLocal()
        try:
            src = create_source(db, {"name": "Auto ID", "channel": "official"})
            _created_ids.append(src.id)
            assert src.id.startswith("src-")
            assert src.name == "Auto ID"
        finally:
            db.close()

    def test_update_source(self):
        from app.services.source_service import create_source, update_source
        sid = _unique_id()
        db = SessionLocal()
        try:
            create_source(db, {"id": sid, "name": "Before", "channel": "rss"})
            _created_ids.append(sid)
            updated = update_source(db, sid, {"name": "After"})
            assert updated.name == "After"
            assert updated.channel == "rss"
        finally:
            db.close()

    def test_update_nonexistent(self):
        from app.services.source_service import update_source
        db = SessionLocal()
        try:
            try:
                update_source(db, "nonexistent-src", {"name": "X"})
                assert False, "Expected HTTPException"
            except HTTPException as e:
                assert e.status_code == 404
        finally:
            db.close()

    def test_delete_source(self):
        from app.services.source_service import create_source, delete_source, get_source
        sid = _unique_id()
        db = SessionLocal()
        try:
            create_source(db, {"id": sid, "name": "ToDelete", "channel": "rss"})
            delete_source(db, sid)
            try:
                get_source(db, sid)
                assert False, "Expected HTTPException"
            except HTTPException as e:
                assert e.status_code == 404
        finally:
            db.close()

    def test_delete_nonexistent(self):
        from app.services.source_service import delete_source
        db = SessionLocal()
        try:
            try:
                delete_source(db, "nonexistent-src")
                assert False, "Expected HTTPException"
            except HTTPException as e:
                assert e.status_code == 404
        finally:
            db.close()

    def test_list_sources_all(self):
        from app.services.source_service import list_sources
        db = SessionLocal()
        try:
            all_srcs = list_sources(db)
            assert isinstance(all_srcs, list)
            assert len(all_srcs) > 0
        finally:
            db.close()

    def test_list_sources_with_channel_filter(self):
        from app.services.source_service import list_sources
        db = SessionLocal()
        try:
            rss_srcs = list_sources(db, channel="rss")
            for s in rss_srcs:
                assert s.channel == "rss"
        finally:
            db.close()

    def test_get_source_found(self):
        from app.services.source_service import create_source, get_source
        sid = _unique_id()
        db = SessionLocal()
        try:
            create_source(db, {"id": sid, "name": "FindMe", "channel": "official"})
            _created_ids.append(sid)
            src = get_source(db, sid)
            assert src.name == "FindMe"
        finally:
            db.close()

    def test_get_source_not_found(self):
        from app.services.source_service import get_source
        db = SessionLocal()
        try:
            try:
                get_source(db, "nonexistent-xyz")
                assert False, "Expected HTTPException"
            except HTTPException as e:
                assert e.status_code == 404
        finally:
            db.close()


class TestSourceAPI:
    """API-level smoke tests for sources."""

    def test_list_sources_api(self):
        resp = client.get("/api/v1/sources")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_create_and_delete_source_api(self):
        sid = _unique_id()
        resp = client.post("/api/v1/sources", json={"id": sid, "name": "API Test", "channel": "web_scrape"})
        assert resp.status_code in (200, 201)
        assert resp.json()["id"] == sid

        resp2 = client.delete(f"/api/v1/sources/{sid}")
        assert resp2.status_code == 200
        assert resp2.json()["ok"] is True
