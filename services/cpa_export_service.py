from __future__ import annotations

import base64
import json
import re
import zipfile
from datetime import datetime, timedelta, timezone
from io import BytesIO
from typing import Any


_CPA_TZ = timezone(timedelta(hours=8))
_UNSAFE_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def decode_jwt_payload(token: str) -> dict[str, Any] | None:
    parts = _clean_text(token).split(".")
    if len(parts) < 2:
        return None

    payload = parts[1]
    padding = "=" * (-len(payload) % 4)
    try:
        raw = base64.urlsafe_b64decode((payload + padding).encode("ascii"))
        decoded = json.loads(raw.decode("utf-8"))
    except Exception:
        return None
    return decoded if isinstance(decoded, dict) else None


def format_cpa_time(timestamp: int | float | str | None) -> str:
    if timestamp is None or timestamp == "":
        return ""
    try:
        value = float(timestamp)
    except (TypeError, ValueError):
        return _clean_text(timestamp)
    try:
        return datetime.fromtimestamp(value, _CPA_TZ).isoformat(timespec="seconds")
    except (OverflowError, OSError, ValueError):
        return ""


def safe_cpa_filename(email: str, index: int) -> str:
    name = _clean_text(email) or f"account-{index + 1}"
    name = _UNSAFE_FILENAME_CHARS.sub("_", name).strip(" .")
    if not name:
        name = f"account-{index + 1}"
    return f"{name}.json"


def _is_disabled(account: dict[str, Any]) -> bool:
    if bool(account.get("disabled")):
        return True
    status = _clean_text(account.get("status"))
    if not status:
        return False
    return status not in {"正常", "active", "enabled", "ok"}


def build_cpa_payload(account: dict[str, Any]) -> dict[str, Any]:
    access_token = _clean_text(account.get("access_token"))
    jwt_payload = decode_jwt_payload(access_token) or {}

    expired = account.get("expired")
    if not expired:
        expired = account.get("expires_at") or jwt_payload.get("exp")

    last_refresh = account.get("last_refresh")
    if not last_refresh:
        last_refresh = account.get("refreshed_at") or jwt_payload.get("iat")

    return {
        "access_token": access_token,
        "account_id": _clean_text(account.get("account_id") or account.get("user_id")),
        "disabled": _is_disabled(account),
        "email": _clean_text(account.get("email")),
        "expired": format_cpa_time(expired),
        "id_token": _clean_text(account.get("id_token")),
        "last_refresh": format_cpa_time(last_refresh),
        "refresh_token": _clean_text(account.get("refresh_token")),
        "type": _clean_text(account.get("cpa_type")) or "codex",
    }


def build_cpa_zip(accounts: list[dict[str, Any]]) -> bytes:
    buffer = BytesIO()
    used_names: dict[str, int] = {}

    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for index, account in enumerate(accounts):
            payload = build_cpa_payload(account)
            base_name = safe_cpa_filename(payload.get("email") or payload.get("account_id"), index)
            name = base_name
            if name in used_names:
                used_names[base_name] += 1
                stem = base_name[:-5] if base_name.endswith(".json") else base_name
                name = f"{stem}-{used_names[base_name]}.json"
            else:
                used_names[base_name] = 1

            archive.writestr(
                name,
                json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"),
            )

    return buffer.getvalue()
