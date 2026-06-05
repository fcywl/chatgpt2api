from __future__ import annotations

from typing import Any

from services.account_service import account_service
from services.openai_backend_api import OpenAIBackendAPI
from utils.helper import IMAGE_MODELS

LOCAL_TEXT_MODELS = {
    "auto",
    "gpt-5",
    "gpt-5-1",
    "gpt-5-2",
    "gpt-5-3",
    "gpt-5-3-mini",
    "gpt-5-mini",
}


def _model_item(model: str, owned_by: str = "chatgpt2api") -> dict[str, Any]:
    return {
        "id": model,
        "object": "model",
        "created": 0,
        "owned_by": owned_by,
        "permission": [],
        "root": model,
        "parent": None,
    }


def _local_catalog() -> dict[str, Any]:
    models = sorted(LOCAL_TEXT_MODELS | IMAGE_MODELS)
    return {"object": "list", "data": [_model_item(model) for model in models]}


def _append_local_models(result: dict[str, Any]) -> dict[str, Any]:
    data = result.get("data")
    if not isinstance(data, list):
        return result
    seen = {str(item.get("id") or "").strip() for item in data if isinstance(item, dict)}
    for model in sorted(LOCAL_TEXT_MODELS | IMAGE_MODELS):
        if model not in seen:
            data.append(_model_item(model))
    return result


def list_models() -> dict[str, Any]:
    access_token = account_service.peek_text_access_token()
    try:
        result = OpenAIBackendAPI(access_token=access_token).list_models()
    except Exception:
        if not access_token:
            return _local_catalog()
        try:
            result = OpenAIBackendAPI().list_models()
        except Exception:
            return _local_catalog()
    return _append_local_models(result)
