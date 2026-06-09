"""
Test notification config CRUD and test-send endpoints.
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from app.main import create_app
from app.database import init_db

app = create_app()
client = TestClient(app)


def setup_module():
    init_db()


# ── CRUD: List ───────────────────────────────────────────────────────

def test_list_notifications_empty() -> None:
    """Listing when no notification configs exist returns empty list."""
    resp = client.get("/api/v1/notifications")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


# ── CRUD: Create ─────────────────────────────────────────────────────

def test_create_webhook_notification() -> None:
    """Create a webhook notification config."""
    resp = client.post("/api/v1/notifications", json={
        "name": "Test Webhook",
        "channel": "webhook",
        "webhook_url": "https://hooks.example.com/test",
        "trigger_on_new": True,
        "trigger_on_failure": False,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Test Webhook"
    assert data["channel"] == "webhook"
    assert data["webhook_url"] == "https://hooks.example.com/test"
    assert data["trigger_on_new"] is True
    assert data["is_active"] is True
    assert "id" in data


def test_create_email_notification() -> None:
    """Create an email notification config."""
    resp = client.post("/api/v1/notifications", json={
        "name": "Test Email",
        "channel": "email",
        "email_to": "test@example.com",
        "trigger_on_failure": True,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["channel"] == "email"
    assert data["email_to"] == "test@example.com"
    assert data["trigger_on_failure"] is True


def test_create_invalid_channel() -> None:
    """Reject unsupported channel types."""
    resp = client.post("/api/v1/notifications", json={
        "name": "Bad",
        "channel": "sms",
    })
    assert resp.status_code == 400


def test_create_webhook_missing_url() -> None:
    """Reject webhook without URL."""
    resp = client.post("/api/v1/notifications", json={
        "name": "No URL",
        "channel": "webhook",
    })
    assert resp.status_code == 400


def test_create_email_missing_to() -> None:
    """Reject email without recipient."""
    resp = client.post("/api/v1/notifications", json={
        "name": "No Email",
        "channel": "email",
    })
    assert resp.status_code == 400


# ── CRUD: Update ─────────────────────────────────────────────────────

def test_update_notification() -> None:
    """Update an existing notification."""
    # First create one
    resp = client.post("/api/v1/notifications", json={
        "name": "Update Me",
        "channel": "webhook",
        "webhook_url": "https://old.example.com",
    })
    notif_id = resp.json()["id"]

    # Then update it
    resp = client.put(f"/api/v1/notifications/{notif_id}", json={
        "name": "Updated Name",
        "webhook_url": "https://new.example.com",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Updated Name"
    assert data["webhook_url"] == "https://new.example.com"


def test_update_nonexistent() -> None:
    """Updating non-existent ID returns 404."""
    resp = client.put("/api/v1/notifications/nonexistent-id", json={"name": "X"})
    assert resp.status_code == 404


# ── CRUD: Test Send ──────────────────────────────────────────────────

def test_test_notification_webhook() -> None:
    """Test-send a notification (should succeed even if URL is fake)."""
    resp = client.post("/api/v1/notifications", json={
        "name": "Test Send Target",
        "channel": "webhook",
        "webhook_url": "https://httpbin.org/post",
    })
    notif_id = resp.json()["id"]

    resp = client.post("/api/v1/notifications/test", json={"id": notif_id})
    assert resp.status_code == 200
    data = resp.json()
    assert "success" in data


def test_test_notification_nonexistent() -> None:
    """Test-sending non-existent ID returns 404."""
    resp = client.post("/api/v1/notifications/test", json={"id": "no-such-id"})
    assert resp.status_code == 404


# ── CRUD: Delete ─────────────────────────────────────────────────────

def test_delete_notification() -> None:
    """Delete an existing notification config."""
    resp = client.post("/api/v1/notifications", json={
        "name": "Delete Me",
        "channel": "webhook",
        "webhook_url": "https://del.example.com",
    })
    notif_id = resp.json()["id"]

    resp = client.delete(f"/api/v1/notifications/{notif_id}")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True

    # Verify it's gone
    resp = client.get("/api/v1/notifications")
    ids = [n["id"] for n in resp.json()]
    assert notif_id not in ids


def test_delete_nonexistent() -> None:
    """Deleting non-existent ID returns 404."""
    resp = client.delete("/api/v1/notifications/nope")
    assert resp.status_code == 404


# ── Toggle active ────────────────────────────────────────────────────

def test_toggle_active() -> None:
    """Toggle is_active via update."""
    resp = client.post("/api/v1/notifications", json={
        "name": "Toggle Test",
        "channel": "webhook",
        "webhook_url": "https://toggle.example.com",
    })
    notif_id = resp.json()["id"]

    # Deactivate
    resp = client.put(f"/api/v1/notifications/{notif_id}", json={"is_active": False})
    assert resp.json()["is_active"] is False

    # Reactivate
    resp = client.put(f"/api/v1/notifications/{notif_id}", json={"is_active": True})
    assert resp.json()["is_active"] is True
