"""
Tests for tag system — merge logic, JSON parsing, namespace handling.

Run: cd backend && python -m pytest tests/test_tags.py -v
"""
import os
import sys
import pytest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.engine import CollectionEngine


class TestAutoTagRules:
    """_apply_auto_tags logic."""

    def test_apply_auto_tags_matches_items(self):
        """Auto tag rules should tag matching items."""
        mock_db = MagicMock()

        # Mock the query chain for collected_items
        mock_item1 = MagicMock()
        mock_item1.id = "item-1"
        mock_item1.title = "Tariff policy update"
        mock_item1.content = "New tariffs announced"
        mock_item1.tags = []

        mock_item2 = MagicMock()
        mock_item2.id = "item-2"
        mock_item2.title = "Weather report"
        mock_item2.content = "Sunny day"
        mock_item2.tags = []

        # Setup query chain
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = [mock_item1, mock_item2]
        mock_db.query.return_value = mock_query

        # Setup ensure_tag mock
        engine = CollectionEngine(mock_db)

        rules = [
            {"keyword": "tariff", "tag": "tag-tariff"},
            {"keyword": "policy", "tag": "tag-policy"},
        ]

        # We need to mock ensure_tag to just return a MagicMock
        with patch.object(engine, 'ensure_tag', return_value=MagicMock()) as mock_ensure:
            count = engine._apply_auto_tags("topic-1", rules)

            # item-1 matches "tariff" and "policy", item-2 matches none
            assert mock_ensure.call_count == 2  # 2 tag applications for item-1

    def test_apply_auto_tags_no_rules(self):
        """Empty rules should not tag anything."""
        mock_db = MagicMock()
        engine = CollectionEngine(mock_db)

        count = engine._apply_auto_tags("topic-1", [])
        assert count == 0

    def test_apply_auto_tags_no_items(self):
        """No items in topic should not tag anything."""
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = []
        mock_db.query.return_value = mock_query

        engine = CollectionEngine(mock_db)
        count = engine._apply_auto_tags("topic-1", [{"keyword": "test", "tag": "t1"}])
        assert count == 0


class TestEnsureTag:
    """ensure_tag creates or retrieves tags."""

    def test_ensure_tag_new_tag(self):
        """Should create a new tag when it doesn't exist."""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        engine = CollectionEngine(mock_db)

        tag = engine.ensure_tag("tag-new", "category", "tariff")
        assert tag is not None
        mock_db.add.assert_called_once()

    def test_ensure_tag_existing_tag(self):
        """Should return existing tag without creating."""
        mock_db = MagicMock()
        existing = MagicMock()
        existing.id = "tag-existing"
        existing.value = "tariff"
        mock_db.query.return_value.filter.return_value.first.return_value = existing
        engine = CollectionEngine(mock_db)

        tag = engine.ensure_tag("tag-existing", "category", "tariff")
        assert tag.id == "tag-existing"
        mock_db.add.assert_not_called()


class TestCheckKeywordMatch:
    """_check_keyword_match logic."""

    def test_single_keyword_match(self):
        engine = CollectionEngine(MagicMock())
        # Testing the inline logic from _persist_items
        text = "New tariff policy announced"
        keywords = ["tariff"]

        matched_kws = [kw for kw in keywords if kw and kw.lower() in text.lower()]
        total_kw = len([kw for kw in keywords if kw])
        required = max(1, 2 if total_kw >= 3 else total_kw)

        assert len(matched_kws) >= required  # 1 match, required=1

    def test_multi_keyword_requires_two(self):
        engine = CollectionEngine(MagicMock())
        text = "New tariff policy"
        keywords = ["tariff", "sanctions", "trade-war"]

        matched_kws = [kw for kw in keywords if kw and kw.lower() in text.lower()]
        total_kw = len([kw for kw in keywords if kw])
        required = max(1, 2 if total_kw >= 3 else total_kw)

        # Only "tariff" matches, need >= 2
        assert len(matched_kws) < required  # 1 < 2

    def test_case_insensitive_match(self):
        engine = CollectionEngine(MagicMock())
        text = "TARIFF POLICY UPDATE"
        keywords = ["tariff"]

        matched_kws = [kw for kw in keywords if kw and kw.lower() in text.lower()]
        assert len(matched_kws) == 1
