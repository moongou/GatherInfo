"""
Test FTS5 full-text search using real database.
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from uuid import uuid4
from datetime import datetime, timezone

from app.database import init_db, SessionLocal
from app.models import CollectedItem
from app.fts_search import search_items, init_fts

_created_ids: list[str] = []


def setup_module():
    init_db()


def _seed(title: str, content: str = "", **kwargs) -> str:
    """Insert a test item and return its ID."""
    db = SessionLocal()
    try:
        it = CollectedItem(
            id=kwargs.pop("id", f"fts-{uuid4().hex[:12]}"),
            source_id=kwargs.pop("source_id", "tavily"),
            title=title,
            content=content,
            collected_at=datetime.now(timezone.utc),
            **kwargs,
        )
        db.add(it)
        db.commit()
        db.refresh(it)
        _created_ids.append(it.id)
        return it.id
    finally:
        db.close()


def teardown_module():
    db = SessionLocal()
    try:
        for cid in _created_ids:
            db.query(CollectedItem).filter(CollectedItem.id == cid).delete()
        db.commit()
    finally:
        db.close()


class TestSearchItems:
    """Test search_items with real DB."""

    def test_empty_query(self) -> None:
        db = SessionLocal()
        try:
            ids, total = search_items(db, "")
            assert isinstance(ids, list)
            assert isinstance(total, int)
        finally:
            db.close()

    def test_keyword_search(self) -> None:
        """Search should find items by keyword in title or content."""
        _seed("Test Customs Tariff Adjustment 2024", "About import tariff changes")
        db = SessionLocal()
        try:
            ids, total = search_items(db, "Tariff")
            assert total >= 1
            assert len(ids) >= 1
        finally:
            db.close()

    def test_title_specific_search(self) -> None:
        """Search should find items by title keyword."""
        _seed("REACH Regulation Update 2024", "EU chemical regulation update")
        db = SessionLocal()
        try:
            ids, total = search_items(db, "REACH")
            assert total >= 1
        finally:
            db.close()

    def test_no_results_for_nonexistent(self) -> None:
        db = SessionLocal()
        try:
            ids, total = search_items(db, "xyznonexistentkeyword99999")
            assert total == 0
            assert ids == []
        finally:
            db.close()

    def test_topic_filter_narrows_results(self) -> None:
        tid = f"topic-fts-{uuid4().hex[:8]}"
        _seed("Topic-specific item", "With topic_id", topic_id=tid)
        db = SessionLocal()
        try:
            ids_all, total_all = search_items(db, "Topic-specific")
            ids_filtered, total_filtered = search_items(db, "Topic-specific", topic_id=tid)
            assert total_filtered <= total_all
        finally:
            db.close()


class TestFTSInit:
    """Test FTS initialization with real engine."""

    def test_init_fts_runs_without_error(self) -> None:
        """init_fts should not crash on real DB."""
        from app.database import engine
        init_fts(engine)
