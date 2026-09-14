from sqlalchemy import text

from app.services.guacamole import check_guacamole_reachable, guacamole_configured


def _check(category, name, status, message, details=None, fix_hint=None):
    return {
        "category": category,
        "name": name,
        "status": status,
        "message": message,
        "details": details or {},
        "fix_hint": fix_hint,
    }


async def run_validation(db):
    checks = []
    nodes = (
        db.execute(text("SELECT COUNT(*) FROM proxmox_nodes")).scalar()
        if db.bind
        else 0
    )
    checks.append(
        _check(
            "nodes",
            "Configured nodes present",
            "pass" if nodes else "warning",
            f"{nodes} nodes configured",
            fix_hint="Add/sync Proxmox nodes from Admin > Proxmox",
        )
    )
    reachable, err = await check_guacamole_reachable()
    checks.append(
        _check(
            "guacamole",
            "Guacamole reachable",
            "pass" if reachable else "error",
            "Private Guacamole gateway reachable"
            if reachable
            else f"Guacamole unreachable: {err}",
            fix_hint="Check the bundled guacd service health in the LabGoblin deployment.",
        )
    )
    checks.append(
        _check(
            "guacamole",
            "Guacamole gateway configured",
            "pass" if guacamole_configured() else "error",
            "Bundled gateway configured; no separate Guacamole login required"
            if guacamole_configured()
            else "Missing private gateway address",
            fix_hint="Restore the bundled guacd service configuration.",
        )
    )
    errors = sum(1 for c in checks if c["status"] == "error")
    warnings = sum(1 for c in checks if c["status"] == "warning")
    passed = sum(1 for c in checks if c["status"] == "pass")
    return {
        "ok": errors == 0,
        "summary": {"errors": errors, "warnings": warnings, "passed": passed},
        "checks": checks,
    }
