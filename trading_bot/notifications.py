"""Notification / alerting system.

Keeps you in the loop on everything the system does without you having to watch
it. Two delivery channels:

* In-app feed   - always on; the dashboard polls /notifications and shows them.
* Email (SMTP)  - optional; enable by setting environment variables (below).
                  Fully failure-tolerant: if email is misconfigured or the SMTP
                  server is unreachable, the trading loop is NEVER affected.

Email setup (optional)
----------------------
    export GUARDIAN_EMAIL_ENABLED=1
    export GUARDIAN_SMTP_HOST=smtp.gmail.com
    export GUARDIAN_SMTP_PORT=587
    export GUARDIAN_SMTP_USER=you@gmail.com
    export GUARDIAN_SMTP_PASS=your_app_password
    export GUARDIAN_EMAIL_TO=you@gmail.com

Severity levels: INFO, SUCCESS, WARNING, CRITICAL.
By default only WARNING and CRITICAL are emailed (configurable) so your inbox
isn't flooded, but EVERYTHING appears in the in-app feed.
"""

import collections
import os
import ssl
import threading
import time


class NotificationCenter:
    def __init__(self, logger=print, max_items=500):
        self.logger = logger
        self._items = collections.deque(maxlen=max_items)
        self._seq = 0
        self._lock = threading.Lock()

        # Email config (read once at startup).
        self.email_enabled = os.environ.get("GUARDIAN_EMAIL_ENABLED", "") in (
            "1", "true", "True", "yes")
        self.smtp_host = os.environ.get("GUARDIAN_SMTP_HOST", "")
        self.smtp_port = int(os.environ.get("GUARDIAN_SMTP_PORT", "587"))
        self.smtp_user = os.environ.get("GUARDIAN_SMTP_USER", "")
        self.smtp_pass = os.environ.get("GUARDIAN_SMTP_PASS", "")
        self.email_to = os.environ.get("GUARDIAN_EMAIL_TO", self.smtp_user)
        # Which severities trigger an email.
        self.email_levels = {"WARNING", "CRITICAL", "SUCCESS"}

    # Common providers -> SMTP host, so users only need their email + password.
    PROVIDERS = {
        "gmail.com": ("smtp.gmail.com", 587),
        "googlemail.com": ("smtp.gmail.com", 587),
        "outlook.com": ("smtp-mail.outlook.com", 587),
        "hotmail.com": ("smtp-mail.outlook.com", 587),
        "live.com": ("smtp-mail.outlook.com", 587),
        "yahoo.com": ("smtp.mail.yahoo.com", 587),
        "icloud.com": ("smtp.mail.me.com", 587),
        "me.com": ("smtp.mail.me.com", 587),
        "aol.com": ("smtp.aol.com", 587),
    }

    def configure_email(self, address, password, send_to=None,
                        smtp_host=None, smtp_port=None):
        """Turn email on at runtime (from the dashboard) — no restart needed.

        We auto-detect the SMTP server from the address domain for common
        providers (Gmail, Outlook, Yahoo, iCloud, AOL). Kept in memory only;
        never written to disk.
        """
        address = (address or "").strip()
        password = (password or "").strip()
        if not address or not password:
            return False, "Email address and password are both required."

        domain = address.split("@")[-1].lower() if "@" in address else ""
        if smtp_host:
            host, port = smtp_host, int(smtp_port or 587)
        elif domain in self.PROVIDERS:
            host, port = self.PROVIDERS[domain]
        else:
            return (False,
                    f"Don't recognise '{domain}'. Enter the SMTP server "
                    f"manually (your email provider lists it).")

        self.smtp_host = host
        self.smtp_port = port
        self.smtp_user = address
        self.smtp_pass = password
        self.email_to = (send_to or address).strip()
        self.email_enabled = True
        return True, f"Email configured for {address} via {host}."

    # ------------------------------------------------------------------ #
    def notify(self, title, message="", level="INFO", email=None):
        """Record a notification and (optionally) email it.

        ``email`` overrides the default per-level emailing decision.
        Returns the notification dict.
        """
        with self._lock:
            self._seq += 1
            item = {
                "id": self._seq,
                "title": title,
                "message": message,
                "level": level,
                "time": time.time(),
                "time_str": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            self._items.appendleft(item)

        self.logger(f"[ALERT:{level}] {title} — {message}")

        should_email = email if email is not None else (level in self.email_levels)
        if should_email and self.email_enabled:
            # Never block / crash the caller on email problems.
            threading.Thread(target=self._send_email_safe,
                             args=(item,), daemon=True).start()
        return item

    # ------------------------------------------------------------------ #
    def recent(self, limit=50, since_id=0):
        with self._lock:
            items = list(self._items)
        out = [i for i in items if i["id"] > since_id]
        return out[:limit]

    def unread_summary(self):
        with self._lock:
            items = list(self._items)
        crit = sum(1 for i in items if i["level"] == "CRITICAL")
        warn = sum(1 for i in items if i["level"] == "WARNING")
        return {"total": len(items), "critical": crit, "warning": warn,
                "latest_id": self._seq,
                "email_active": self.email_enabled}

    # ------------------------------------------------------------------ #
    def send_test(self):
        """Send a test email SYNCHRONOUSLY and report success/failure.

        Unlike normal notifications (fire-and-forget), this returns a detailed
        result dict so the UI can tell you exactly whether your inbox is wired
        up correctly BEFORE you rely on alerts in a live session.
        """
        # Always record the attempt in the in-app feed.
        self.notify("✉️ Test alert", "This is a test of your alert system.",
                    level="INFO", email=False)

        if not self.email_enabled:
            return {
                "ok": False,
                "emailed": False,
                "reason": "Email is not enabled. Set GUARDIAN_EMAIL_ENABLED=1 "
                          "and the SMTP env vars, then restart.",
                "config": self._config_summary(),
            }
        missing = [name for name, val in (
            ("GUARDIAN_SMTP_HOST", self.smtp_host),
            ("GUARDIAN_SMTP_USER", self.smtp_user),
            ("GUARDIAN_EMAIL_TO", self.email_to),
        ) if not val]
        if missing:
            return {
                "ok": False,
                "emailed": False,
                "reason": f"Missing required settings: {', '.join(missing)}",
                "config": self._config_summary(),
            }

        item = {
            "title": "Test alert — your inbox is connected",
            "message": ("If you can read this, your AI Trading Guardian email "
                        "alerts are working. You'll be notified of day start, "
                        "approaching/hit limits, and shutdowns."),
            "level": "INFO",
            "time_str": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        try:
            self._send_email(item)
            return {
                "ok": True,
                "emailed": True,
                "reason": f"Test email sent to {self.email_to}. Check your inbox "
                          f"(and spam folder).",
                "config": self._config_summary(),
            }
        except Exception as exc:
            return {
                "ok": False,
                "emailed": False,
                "reason": f"SMTP error: {exc}",
                "config": self._config_summary(),
            }

    def _config_summary(self):
        """Non-sensitive view of the email config (password never exposed)."""
        return {
            "enabled": self.email_enabled,
            "smtp_host": self.smtp_host or "(unset)",
            "smtp_port": self.smtp_port,
            "smtp_user": self.smtp_user or "(unset)",
            "email_to": self.email_to or "(unset)",
            "password_set": bool(self.smtp_pass),
        }

    def _send_email_safe(self, item):
        try:
            self._send_email(item)
        except Exception as exc:  # pragma: no cover - network dependent
            self.logger(f"Email send failed (non-fatal): {exc}")

    def _send_email(self, item):
        import smtplib
        from email.mime.text import MIMEText

        if not (self.smtp_host and self.smtp_user and self.email_to):
            return
        subject = f"[AI Guardian {item['level']}] {item['title']}"
        body = (f"{item['title']}\n\n{item['message']}\n\n"
                f"Time: {item['time_str']}\n"
                f"Severity: {item['level']}\n\n"
                f"— AI Trading Guardian")
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = self.smtp_user
        msg["To"] = self.email_to

        context = ssl.create_default_context()
        with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=15) as server:
            server.ehlo()
            try:
                server.starttls(context=context)
                server.ehlo()
            except Exception:
                pass  # server may not support STARTTLS
            if self.smtp_pass:
                server.login(self.smtp_user, self.smtp_pass)
            server.sendmail(self.smtp_user, [self.email_to], msg.as_string())
        self.logger(f"Email sent: {item['title']}")
