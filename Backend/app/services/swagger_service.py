"""
swagger_service.py — Fetches, parses, and caches the OpenAPI spec at startup.
The cached catalog is injected into LLM prompts as grounding context.
"""
import logging
import copy
import requests

logger = logging.getLogger(__name__)

# Module-level singleton — populated by load_catalog() at startup
_catalog: dict | None = None


def _resolve_refs(obj: dict | list, root: dict) -> dict | list:
    """Recursively inline all $ref references in an OpenAPI object."""
    if isinstance(obj, dict):
        if "$ref" in obj:
            ref_path = obj["$ref"]  # e.g. "#/components/schemas/Foo"
            parts = ref_path.lstrip("#/").split("/")
            resolved = root
            for part in parts:
                resolved = resolved.get(part, {})
            return _resolve_refs(copy.deepcopy(resolved), root)
        return {k: _resolve_refs(v, root) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_resolve_refs(item, root) for item in obj]
    return obj


def _parse_spec(spec: dict) -> dict:
    """Convert a raw OpenAPI spec dict into the simplified catalog shape."""
    endpoints = []
    paths = spec.get("paths", {})
    http_methods = {"get", "post", "put", "patch", "delete", "head", "options"}

    for path, path_item in paths.items():
        for method, operation in path_item.items():
            if method.lower() not in http_methods:
                continue
            if not isinstance(operation, dict):
                continue

            entry = {
                "path": path,
                "method": method.upper(),
                "summary": operation.get("summary", ""),
                "parameters": _resolve_refs(operation.get("parameters", []), spec),
                "request_body": _resolve_refs(
                    operation.get("requestBody", None) or {}, spec
                ) or None,
                "responses": _resolve_refs(operation.get("responses", {}), spec),
            }
            endpoints.append(entry)

    return {"endpoints": endpoints}


def load_catalog(swagger_url: str | None) -> None:
    """
    Fetch and parse the OpenAPI spec from swagger_url.
    Supports both HTTP URLs and local file paths.
    Stores the result in the module-level _catalog variable.
    On any error, logs a warning and sets _catalog to None.
    """
    global _catalog

    if not swagger_url:
        logger.warning("SWAGGER_URL is not set — API catalog will not be available.")
        _catalog = None
        return

    try:
        # Check if it's a local file path
        if swagger_url.startswith("file://") or not swagger_url.startswith("http"):
            # Local file
            import json
            file_path = swagger_url.replace("file://", "")
            with open(file_path, 'r') as f:
                spec = json.load(f)
        else:
            # HTTP URL
            import os
            headers = {}
            cookies = {}
            
            # Support Bearer token auth
            auth_token = os.getenv("SWAGGER_AUTH_TOKEN")
            if auth_token:
                headers["Authorization"] = f"Bearer {auth_token}"
            
            # Support cookie-based auth
            swagger_cookie = os.getenv("SWAGGER_COOKIE")
            if swagger_cookie:
                # Parse cookie string like "access_token_dev=xxx"
                for cookie_pair in swagger_cookie.split(';'):
                    cookie_pair = cookie_pair.strip()
                    if '=' in cookie_pair:
                        key, value = cookie_pair.split('=', 1)
                        cookies[key.strip()] = value.strip()
                logger.info(f"Using {len(cookies)} cookie(s) for Swagger authentication")
            
            response = requests.get(
                swagger_url, 
                headers=headers, 
                cookies=cookies,
                timeout=30, 
                allow_redirects=False
            )
            
            logger.info(f"Swagger response status: {response.status_code}")
            
            # If we get a redirect to auth, log a helpful message
            if response.status_code in (301, 302, 307, 308):
                logger.warning(
                    "Swagger URL requires authentication (got redirect). "
                    "Set SWAGGER_AUTH_TOKEN or SWAGGER_COOKIE in .env, or use a local file path."
                )
                _catalog = None
                return
            
            response.raise_for_status()
            spec = response.json()
        
        _catalog = _parse_spec(spec)
        endpoint_count = len(_catalog.get("endpoints", []))
        logger.info("API catalog loaded: %d endpoints from %s", endpoint_count, swagger_url)
    except Exception as exc:
        logger.warning("Failed to load API catalog from %s: %s", swagger_url, exc)
        _catalog = None


def get_catalog() -> dict | None:
    """Return the cached API catalog, or None if not loaded."""
    return _catalog
