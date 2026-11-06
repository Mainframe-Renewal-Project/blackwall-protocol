import json
import logging
import os
from dataclasses import fields
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

JOURNAL_PATH = Path.home() / ".config" / "blackwall" / "backout.json"
MAX_RECORDS = 500

logger = logging.getLogger(__name__)

def _read_records() -> list[dict[str, Any]]:
    if not JOURNAL_PATH.exists():
        return []
    journal = json.loads(JOURNAL_PATH.read_text(encoding="utf-8"))
    return journal.get("records", [])


def _write_records(records: list[dict[str, Any]]) -> None:
    JOURNAL_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = JOURNAL_PATH.with_suffix(".tmp")
    file_descriptor = os.open(
        temporary_path,
        os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
        0o600,
    )
    with os.fdopen(file_descriptor, "w", encoding="utf-8") as journal_file:
        json.dump({"version": 1, "records": records[-MAX_RECORDS:]}, journal_file)
    temporary_path.replace(JOURNAL_PATH)
    JOURNAL_PATH.chmod(0o600)


def get_change_records() -> list[dict[str, Any]]:
    return list(reversed(_read_records()))


def _trait_models(admin_type: str) -> dict[str, type]:
    if admin_type == "user":
        from blackwall.api import user

        return {
            "base": user.BaseUserTraits,
            "tso": user.TSOUserTraits,
            "omvs": user.OMVSUserTraits,
            "cics": user.CICSUserTraits,
            "kerb": user.KerbUserTraits,
            "eim": user.EIMUserTraits,
            "language": user.LanguageUserTraits,
            "dce": user.DCEUserTraits,
            "dfp": user.DFPUserTraits,
            "nds": user.NDSUserTraits,
            "lnotes": user.LnotesUserTraits,
            "mfa": user.MfaUserTraits,
            "ovm": user.OvmUserTraits,
            "proxy": user.ProxyUserTraits,
            "workattr": user.WorkattrUserTraits,
            "netview": user.NetviewUserTraits,
            "operparm": user.OperparmUserTraits,
        }
    if admin_type == "group":
        from blackwall.api import group

        return {
            "base": group.BaseGroupTraits,
            "tme": group.TMEGroupTraits,
            "omvs": group.OMVSGroupTraits,
            "dfp": group.DFPGroupTraits,
            "ovm": group.OVMGroupTraits,
        }
    if admin_type == "dataset":
        from blackwall.api import dataset

        return {
            "base": dataset.BaseDatasetTraits,
            "dfp": dataset.DFPDatasetTraits,
            "tme": dataset.TMEDatasetTraits,
        }
    if admin_type == "resource":
        from blackwall.api import resource

        return {
            "base": resource.BaseResourceTraits,
            "kerb": resource.KerbResourceTraits,
            "dlf": resource.DLFDataResourceTraits,
            "eim": resource.EIMResourceTraits,
            "jes": resource.JESResourceTraits,
            "icsf": resource.ICSFResourceTraits,
            "ictx": resource.ICTXResourceTraits,
            "idtparms": resource.IDTPARMSResourceTraits,
            "session": resource.SessionResourceTraits,
            "svfmr": resource.SVFMRResourceTraits,
            "stdata": resource.STDATAResourceTraits,
            "proxy": resource.ProxyResourceTraits,
            "mfpolicy": resource.MFPolicyResourceTraits,
            "sigver": resource.SIGVERResourceTraits,
            "tme": resource.TMEResourceTraits,
            "cdtinfo": resource.CDTINFOResourceTraits,
            "ssignon": resource.SSIGNONResourceTraits,
            "cfdef": resource.CfdefResourceTraits,
        }
    return {}


def _is_scalar(value: Any) -> bool:
    return isinstance(value, (str, int, bool))


def _restore_traits(
    admin_type: str,
    profile: dict[str, Any],
    operation: str,
) -> tuple[dict[str, Any], bool]:
    traits = {}
    incomplete = False
    models = _trait_models(admin_type)

    for segment, values in profile.items():
        model = models.get(segment)
        if model is None or not isinstance(values, dict):
            incomplete = True
            continue

        model_fields = {field.name: field for field in fields(model)}
        known_keys = set()
        for field in model_fields.values():
            key = f"{segment}:{field.name}"
            if key not in values:
                continue
            known_keys.add(key)
            allowed_in = field.metadata.get("allowed_in")
            value = values[key]
            if (
                field.metadata.get("masked", False)
                or (allowed_in is not None and operation not in allowed_in)
                or not _is_scalar(value)
            ):
                incomplete = True
                continue
            traits[key] = value
        if set(values) - known_keys:
            incomplete = True

    return traits, incomplete


def _inverse_request(
    admin_type: str,
    identity: dict[str, str],
    operation: str,
    before_profile: dict[str, Any] | None,
    changed_traits: dict[str, Any] | None,
) -> tuple[dict[str, Any] | None, str | None]:
    if operation == "add":
        return {"operation": "delete", "admin_type": admin_type, **identity}, None

    if before_profile is None:
        return None, "The previous profile state could not be captured."

    if operation == "delete":
        traits, incomplete = _restore_traits(admin_type, before_profile, "add")
        if not traits:
            return None, "No writable profile traits were available to restore."
        restore_request = {
            "operation": "add",
            "admin_type": admin_type,
            **identity,
            "traits": traits,
        }
        if admin_type == "dataset":
            base_profile = before_profile.get("base", {})
            is_generic = base_profile.get("base:is_generic")
            if is_generic is True:
                restore_request["generic"] = True
            elif is_generic is None and "*" in identity.get("dataset", ""):
                return None, "The deleted dataset profile's generic status could not be determined."
        warning = None
        if incomplete:
            warning = "Some credentials, read-only traits, or repeated traits cannot be restored."
        return restore_request, warning

    if operation == "alter":
        models = _trait_models(admin_type)
        inverse_traits = {}
        for key in changed_traits or {}:
            if ":" not in key:
                return None, "A changed trait could not be identified safely."
            segment, field_name = key.split(":", 1)
            model = models.get(segment)
            field_map = {field.name: field for field in fields(model)} if model else {}
            field = field_map.get(field_name)
            old_segment = before_profile.get(segment, {})
            if (
                field is None
                or field.metadata.get("masked", False)
                or key not in old_segment
                or not _is_scalar(old_segment[key])
            ):
                return None, "A changed trait had no safely restorable prior value."
            inverse_traits[key] = old_segment[key]
        if not inverse_traits:
            return None, "No safely restorable traits were changed."
        return {
            "operation": "alter",
            "admin_type": admin_type,
            **identity,
            "traits": inverse_traits,
        }, None

    return None, "This operation has no automatic backout handler."


def record_profile_change(
    *,
    admin_type: str,
    identity: dict[str, str],
    operation: str,
    description: str,
    before_profile: dict[str, Any] | None = None,
    changed_traits: dict[str, Any] | None = None,
) -> None:
    try:
        undo_request, undo_warning = _inverse_request(
            admin_type,
            identity,
            operation,
            before_profile,
            changed_traits,
        )
        records = _read_records()
        records.append(
            {
                "id": uuid4().hex,
                "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
                "description": description,
                "undo_request": undo_request,
                "undo_warning": undo_warning,
                "status": "available" if undo_request is not None else "unavailable",
            },
        )
        _write_records(records)
    except (OSError, ValueError):
        logger.exception("Could not write the Blackwall backout journal")


def undo_change(record_id: str) -> tuple[int, str]:
    records = _read_records()
    record = next((item for item in records if item["id"] == record_id), None)
    if record is None:
        return 8, "Backout record was not found."
    if record["status"] != "available" or record["undo_request"] is None:
        return 8, record.get("undo_warning") or "This change is not available for backout."

    request = record["undo_request"]
    from blackwall.api import dataset, group, resource, user

    api_modules = {
        "user": user,
        "group": group,
        "dataset": dataset,
        "resource": resource,
    }
    api_module = api_modules[request["admin_type"]]
    if not api_module.sear_enabled:
        return 8, "SEAR is unavailable."

    result = api_module.sear(request)
    return_code = result.result["return_codes"]["racf_return_code"]
    if return_code in {0, 4}:
        record["status"] = "backed_out"
        record["backed_out_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
        _write_records(records)
    return return_code, "Backout completed." if return_code in {0, 4} else "SEAR rejected the backout request."