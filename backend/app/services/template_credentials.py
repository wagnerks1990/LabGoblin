"""Template secrets: explicit write, server-side use, and authorized VM disclosure."""

import json

from fastapi import HTTPException

from app.models.models import VMTemplate, TemplateGuestCredential
from app.services.secret_crypto import decrypt_secret


def template_for_vm(db, vm):
    template = db.get(VMTemplate, vm.template_id)
    if (
        not template
        or template.organization_id != vm.organization_id
        or not template.enabled
    ):
        raise HTTPException(409, "This VM's template is unavailable.")
    credential = db.get(TemplateGuestCredential, template.id)
    if not credential:
        raise HTTPException(
            409, "No guest credentials are configured for this template."
        )
    return credential


def decode_credentials(encrypted):
    try:
        data = json.loads(decrypt_secret(encrypted))
        if not all(
            isinstance(data.get(key), str) and data[key]
            for key in ("username", "password")
        ):
            raise ValueError()
        return {
            "username": data["username"],
            "password": data["password"],
            "domain": data.get("domain", ""),
        }
    except Exception:
        raise HTTPException(
            503, "Stored guest credentials could not be read."
        ) from None


def connection_credentials(db, vm, profile):
    if profile.encrypted_credentials:
        return decode_credentials(profile.encrypted_credentials)
    credential = template_for_vm(db, vm)
    if not credential.auto_connect:
        raise HTTPException(
            403, "Automatic connections using template credentials are disabled."
        )
    return decode_credentials(credential.encrypted_credentials)


def template_connection_revision(db, vm, profile):
    if profile.encrypted_credentials:
        return None
    credential = template_for_vm(db, vm)
    return credential.revision, credential.auto_connect
