"""Tests for the notification center (in-app feed; email is opt-in)."""

import pytest

from trading_bot.notifications import NotificationCenter


def make():
    return NotificationCenter(logger=lambda *_: None)


def test_notify_records_item():
    n = make()
    item = n.notify("Title", "body", level="INFO")
    assert item["title"] == "Title"
    assert item["level"] == "INFO"
    assert n.recent()[0]["title"] == "Title"


def test_recent_since_id_filters():
    n = make()
    a = n.notify("A")
    b = n.notify("B")
    newer = n.recent(since_id=a["id"])
    titles = [i["title"] for i in newer]
    assert "B" in titles and "A" not in titles


def test_summary_counts_levels():
    n = make()
    n.notify("x", level="CRITICAL")
    n.notify("y", level="WARNING")
    n.notify("z", level="INFO")
    s = n.unread_summary()
    assert s["critical"] == 1
    assert s["warning"] == 1
    assert s["total"] == 3


def test_email_disabled_by_default():
    n = make()
    # No env vars set in test -> email disabled, notify must not raise.
    n.notify("safe", level="CRITICAL")
    assert n.email_enabled is False


def test_ordering_newest_first():
    n = make()
    n.notify("first")
    n.notify("second")
    assert n.recent()[0]["title"] == "second"


def test_send_test_reports_disabled_clearly():
    n = make()  # email not enabled in tests
    res = n.send_test()
    assert res["ok"] is False
    assert res["emailed"] is False
    assert "not enabled" in res["reason"].lower()
    # The test attempt is still logged to the in-app feed.
    assert any("Test alert" in i["title"] for i in n.recent())


def test_config_summary_never_exposes_password():
    n = make()
    n.smtp_pass = "supersecret"
    summary = n._config_summary()
    assert "supersecret" not in str(summary)
    assert summary["password_set"] is True


def test_configure_email_autodetects_gmail():
    n = make()
    ok, msg = n.configure_email("someone@gmail.com", "apppassword")
    assert ok is True
    assert n.smtp_host == "smtp.gmail.com"
    assert n.smtp_port == 587
    assert n.email_enabled is True
    assert n.email_to == "someone@gmail.com"


def test_configure_email_autodetects_outlook():
    n = make()
    ok, _ = n.configure_email("me@outlook.com", "pw")
    assert ok is True
    assert n.smtp_host == "smtp-mail.outlook.com"


def test_configure_email_unknown_provider_needs_manual():
    n = make()
    ok, msg = n.configure_email("me@somerandomco.xyz", "pw")
    assert ok is False
    assert "smtp" in msg.lower()
    assert n.email_enabled is False


def test_configure_email_manual_host():
    n = make()
    ok, _ = n.configure_email("me@somerandomco.xyz", "pw",
                              smtp_host="mail.somerandomco.xyz", smtp_port=465)
    assert ok is True
    assert n.smtp_host == "mail.somerandomco.xyz"
    assert n.smtp_port == 465


def test_configure_email_requires_both_fields():
    n = make()
    ok, _ = n.configure_email("me@gmail.com", "")
    assert ok is False


def test_configure_email_separate_send_to():
    n = make()
    n.configure_email("sender@gmail.com", "pw", send_to="alerts@gmail.com")
    assert n.smtp_user == "sender@gmail.com"
    assert n.email_to == "alerts@gmail.com"


def test_send_test_delivers_via_smtp():
    """End-to-end: with a real (local) SMTP server, the test email is sent."""
    aiosmtpd = pytest.importorskip("aiosmtpd")
    from aiosmtpd.controller import Controller

    class Handler:
        def __init__(self):
            self.messages = []

        async def handle_DATA(self, server, session, envelope):
            self.messages.append(envelope.content)
            return "250 OK"

    handler = Handler()
    controller = Controller(handler, hostname="127.0.0.1", port=8121)
    controller.start()
    try:
        n = NotificationCenter(logger=lambda *_: None)
        n.email_enabled = True
        n.smtp_host = "127.0.0.1"
        n.smtp_port = 8121
        n.smtp_user = "guardian@test.local"
        n.smtp_pass = ""
        n.email_to = "me@test.local"
        res = n.send_test()
        import time as _t
        _t.sleep(0.5)
        assert res["ok"] is True
        assert len(handler.messages) == 1
        assert b"me@test.local" in handler.messages[0]
    finally:
        controller.stop()
