#!/usr/bin/env python3
"""Root-only Resend enrollment. Secrets travel through stdin, never argv/logs."""

import argparse
import http.client
import json
import os
from pathlib import Path
import stat
import subprocess
import urllib.error
import urllib.request
from urllib.parse import urlsplit
from uuid import UUID

EVENTS = [
    "email.received",
    "email.sent",
    "email.delivered",
    "email.bounced",
    "email.complained",
    "email.failed",
    "email.delivery_delayed",
    "email.suppressed",
]

IMPORT_CONFIGURATION = """
import json, sys
from app.db.session import SessionLocal
from app.schemas.email import EmailConfiguration
from app.services.email_service import save_configuration
from app.services.audit_service import record_audit_event
with SessionLocal() as db:
    save_configuration(db, EmailConfiguration(**json.load(sys.stdin)))
    record_audit_event(db, action='email.host_enrolled', target_type='email_settings', target_id='1')
    db.commit()
"""


def protected_key(path):
    info = path.stat()
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_uid != 0
        or stat.S_IMODE(info.st_mode) != 0o600
    ):
        raise ValueError(
            "API key file must be a root-owned regular file with mode 0600"
        )
    key = path.read_text().strip()
    if not key.startswith("re_") or len(key) > 1024 or any(c.isspace() for c in key):
        raise ValueError("Invalid API key file format")
    return key


def api(key, method, path, body=None):
    request = urllib.request.Request(
        "https://api.resend.com" + path,
        method=method,
        headers={
            "Authorization": "Bearer " + key,
            "Content-Type": "application/json",
            "User-Agent": "LabGoblin enrollment",
        },
        data=json.dumps(body).encode() if body is not None else None,
    )

    # The provider is fixed; reject redirects rather than forwarding the key.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    try:
        with urllib.request.build_opener(NoRedirect).open(
            request, timeout=20
        ) as response:
            return json.loads(response.read(2_000_000))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(
            f"Resend request failed (HTTP {exc.code}); no provider body displayed"
        ) from None
    except (urllib.error.URLError, ValueError):
        raise RuntimeError(
            "Resend connection failed; no credential values displayed"
        ) from None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--key-file", type=Path, required=True)
    parser.add_argument("--origin", required=True)
    parser.add_argument("--sender", required=True)
    parser.add_argument("--support", required=True)
    parser.add_argument("--enable-notifications", action="store_true")
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise ValueError("Run as root on the Docker deployment host")
    parsed = urlsplit(args.origin)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
        or parsed.port not in {None, 443}
    ):
        raise ValueError("Use an exact HTTPS origin")
    origin = "https://" + parsed.hostname
    app = Path(__file__).resolve().parents[1]
    env = dict(
        line.split("=", 1)
        for line in (app / ".env").read_text().splitlines()
        if line and not line.startswith("#") and "=" in line
    )
    if origin not in env.get("BROWSER_TRUSTED_ORIGINS", "").split(","):
        raise ValueError("Origin must already be in BROWSER_TRUSTED_ORIGINS")
    if env.get("CLOUDFLARE_ACCESS_REQUIRED", "false").lower() == "true":
        raise ValueError(
            "Access-required deployments need a reviewed provider-authenticated delivery path; this helper does not bypass Access"
        )
    key = protected_key(args.key_file)
    domains = api(key, "GET", "/domains").get("data", [])
    for email in [args.sender, args.support]:
        if "\n" in email or "\r" in email or email.count("@") != 1:
            raise ValueError("Invalid email address")
        domain = next(
            (d for d in domains if d.get("name") == email.split("@")[1]), None
        )
        if not domain or domain.get("status") != "verified":
            raise ValueError("Sender and support domains must be verified in Resend")
    endpoint = origin + "/api/email/resend/webhook"
    # Readiness first: never register a callback into an unhealthy release.
    connection = http.client.HTTPSConnection(parsed.hostname, timeout=20)
    try:
        connection.request("GET", "/api/ready")
        response = connection.getresponse()
        if response.status != 200 or not json.load(response).get("ready"):
            raise ValueError("Application is not ready")
    finally:
        connection.close()
    matches = [
        v
        for v in api(key, "GET", "/webhooks").get("data", [])
        if v.get("endpoint") == endpoint
    ]
    if len(matches) > 1:
        raise ValueError(
            "Duplicate matching webhooks; review in Resend before continuing"
        )
    if matches:
        webhook = api(key, "GET", "/webhooks/" + str(UUID(matches[0]["id"])))
        if not set(EVENTS).issubset(set(webhook.get("events", []))):
            raise ValueError(
                "Existing endpoint is missing required email events; update it in Resend and rerun"
            )
    else:
        webhook = api(
            key, "POST", "/webhooks", {"endpoint": endpoint, "events": EVENTS}
        )
    payload = {
        "enabled": True,
        "receiving_enabled": True,
        "notifications_enabled": args.enable_notifications,
        "public_origin": origin,
        "sender": args.sender,
        "support_address": args.support,
        "api_key": key,
        "webhook_secret": webhook["signing_secret"],
    }
    result = subprocess.run(
        [
            "docker",
            "compose",
            "--project-directory",
            str(app),
            "--env-file",
            str(app / ".env"),
            "exec",
            "-T",
            "api",
            "python",
            "-c",
            IMPORT_CONFIGURATION,
        ],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode:
        raise RuntimeError(
            "Could not import email configuration. Check the deployed migration and container; no credential values displayed"
        )
    state = Path("/var/lib/labgoblin/resend.json")
    fd = os.open(state, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as output:
        json.dump(
            {"webhook_id": str(UUID(webhook["id"])), "endpoint": endpoint},
            output,
            indent=2,
        )
    print(
        "Resend configured. Sending and support receiving enabled. No test messages were sent."
    )
    print("Webhook resource ID:", webhook["id"])


if __name__ == "__main__":
    try:
        main()
    except (
        ValueError,
        RuntimeError,
        OSError,
        KeyError,
        subprocess.TimeoutExpired,
    ) as exc:
        raise SystemExit(str(exc)) from None
