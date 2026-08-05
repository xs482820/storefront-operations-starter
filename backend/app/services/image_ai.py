import base64
import binascii
import logging
from pathlib import Path

import httpx

from app.core.exceptions import bad_request

logger = logging.getLogger(__name__)

IMAGE_CONTENT_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


def _image_service_settings(settings: dict) -> tuple[str, str, str]:
    base_url = str(settings.get("base_url") or "").rstrip("/")
    model = str(settings.get("model") or "").strip()
    api_key = str(settings.get("api_key") or "").strip()
    if not settings.get("enabled"):
        raise bad_request("image service is disabled")
    if not base_url or not model or not api_key:
        raise bad_request("image service is not configured")
    return base_url, model, api_key


async def test_store_image_service(*, settings: dict) -> dict[str, str | int | bool]:
    """Check a compatible provider without submitting a paid image generation."""
    base_url, model, api_key = _image_service_settings(settings)
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(f"{base_url}/models", headers={"Authorization": f"Bearer {api_key}"})
    except httpx.TimeoutException as error:
        raise bad_request("image service connection timed out after 20s") from error
    except httpx.HTTPError as error:
        raise bad_request("image service connection failed") from error

    if response.status_code == 401:
        raise bad_request("image service authentication failed (HTTP 401)")
    if response.status_code == 403:
        raise bad_request("image service does not permit this key (HTTP 403)")
    if response.status_code == 404:
        return {"ok": False, "status_code": 404, "message": "service does not provide a model-list endpoint; generation was not attempted"}
    if response.status_code >= 400:
        raise bad_request(f"image service connection failed (HTTP {response.status_code})")
    return {"ok": True, "status_code": response.status_code, "message": f"connection and authentication succeeded; configured model: {model}"}


def detect_image_content_type(content: bytes) -> str | None:
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if content.startswith(b"RIFF") and content[8:12] == b"WEBP":
        return "image/webp"
    return None


async def generate_store_image(*, settings: dict, prompt: str, reference_paths: list[Path]) -> bytes:
    base_url, model, api_key = _image_service_settings(settings)

    request_data = {
        "model": model,
        "prompt": prompt,
    }
    headers = {"Authorization": f"Bearer {api_key}"}
    endpoint = f"{base_url}/images/edits" if reference_paths else f"{base_url}/images/generations"
    timeout = max(15, min(int(settings.get("timeout_seconds") or 90), 180))

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            if reference_paths:
                files = [
                    ("image[]", (path.name, path.read_bytes(), IMAGE_CONTENT_TYPES[path.suffix.lower()]))
                    for path in reference_paths
                ]
                response = await client.post(endpoint, headers=headers, data=request_data, files=files)
            else:
                response = await client.post(endpoint, headers=headers, json=request_data)
            response.raise_for_status()
            payload = response.json()
            image = (payload.get("data") or [{}])[0]
            encoded = image.get("b64_json") if isinstance(image, dict) else None
            if encoded:
                return base64.b64decode(encoded)
            image_url = image.get("url") if isinstance(image, dict) else None
            if image_url:
                download = await client.get(image_url)
                download.raise_for_status()
                return download.content
    except httpx.TimeoutException as error:
        logger.warning("image generation request timed out after %ss", timeout)
        raise bad_request(f"image service timed out after {timeout}s") from error
    except httpx.HTTPError as error:
        status = error.response.status_code if isinstance(error, httpx.HTTPStatusError) else None
        logger.warning("image generation request failed: %s", error)
        if status == 401:
            raise bad_request("image service authentication failed (HTTP 401)") from error
        if status == 403:
            raise bad_request("image service does not permit this model or operation (HTTP 403)") from error
        suffix = f" (HTTP {status})" if status else ""
        raise bad_request(f"image service request failed{suffix}") from error
    except (TypeError, ValueError, binascii.Error) as error:
        logger.warning("image generation response was invalid: %s", error)
        raise bad_request("image service returned an invalid image") from error
    raise bad_request("image service did not return an image")
