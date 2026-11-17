"""GET /api/v1/operations/ecosystem: aggregate the status of every ecosystem service named in the registry.

Standalone rule: this never fails because a sibling is offline. Each service is probed concurrently with a short timeout,
validated against the service-manifest contract and cached briefly. Only http(s) to loopback is contacted unless the host is
listed in ASAA_AP_ECOSYSTEM_ALLOWED_HOSTS. Base URLs can be overridden with ASAA_AP_ECOSYSTEM_<SERVICE>_URL.
"""
import ipaddress
import json
import os
import re
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends

from asaa_ap.config import get_settings
from asaa_ap.security import Principal, require_permission
from asaa_integration.manifest import SERVICE_ID, build_manifest

router = APIRouter(tags=["Operations"])

PROBE_TIMEOUT_SECONDS = 2.0
CACHE_TTL_SECONDS = 15.0
MAX_BODY_BYTES = 64 * 1024
REGISTRY_RELATIVE = Path("contracts") / "ecosystem" / "v1" / "ecosystem-registry.json"
PROJECTS = {"ASAA", "JARVIS", "TEMPLATES", "PORTFOLIO"}
STATES = {"ok", "degraded", "down"}
_SERVICE = re.compile(r"^[a-z][a-z0-9-]{1,39}$")
_CAPABILITY = re.compile(r"^[a-z][a-z0-9.-]{1,63}$")
_COMMIT = re.compile(r"^[0-9a-f]{7,40}$")
_CONTRACT_VERSION = re.compile(r"^v[0-9]+$")
_MANIFEST_KEYS = {"schema", "service", "project", "version", "commit", "environment", "status", "checkedAt", "checks", "capabilities", "contracts"}
_MANIFEST_REQUIRED = {"schema", "service", "project", "version", "status", "checkedAt", "checks", "capabilities"}

_cache_lock = threading.Lock()
_cache: dict = {}


def reset_cache() -> None:
    with _cache_lock:
        _cache.clear()


def _now() -> float:
    return time.monotonic()


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


# ---------------------------------------------------------------- registry

def registry_path() -> Path | None:
    configured = get_settings().ecosystem_registry_path
    if configured:
        return Path(configured)
    for base in (Path.cwd(), *Path(__file__).resolve().parents):
        candidate = base / REGISTRY_RELATIVE
        if candidate.is_file():
            return candidate
    return None


def load_registry() -> tuple[dict | None, str | None]:
    path = registry_path()
    if path is None or not path.is_file():
        return None, "registry file not found"
    try:
        registry = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None, "registry file is not valid JSON"
    if not isinstance(registry, dict) or registry.get("schema") != "asaa.ecosystem-registry.v1" or not isinstance(registry.get("projects"), list):
        return None, "registry file does not match asaa.ecosystem-registry.v1"
    return registry, None


# ---------------------------------------------------------------- URL policy

def base_url_for(service: dict) -> str | None:
    override = os.environ.get("ASAA_AP_ECOSYSTEM_" + re.sub(r"[^A-Z0-9]", "_", str(service.get("service", "")).upper()) + "_URL")
    if override:
        return override
    order = ("localProdBaseUrl", "devBaseUrl") if get_settings().environment == "production" else ("devBaseUrl", "localProdBaseUrl")
    for key in order:
        if service.get(key):
            return service[key]
    return None


def url_allowed(url: str, allowed_hosts: list[str]) -> bool:
    try:
        parts = urlsplit(url)
        host = parts.hostname
    except ValueError:
        return False
    if parts.scheme not in {"http", "https"} or not host or parts.username or parts.password:
        return False
    if host in {h.lower() for h in allowed_hosts}:
        return True
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


# ---------------------------------------------------------------- transport (replaced by a fake in tests)

class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):  # noqa: D401 - never follow redirects off the allowlisted host
        return None


def default_transport(url: str, timeout: float) -> tuple[int, bytes]:
    opener = urllib.request.build_opener(_NoRedirect)
    request = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "asaa-ecosystem-status/1"})
    try:
        with opener.open(request, timeout=timeout) as response:  # noqa: S310 - scheme and host are validated by url_allowed
            return response.status, response.read(MAX_BODY_BYTES + 1)
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(MAX_BODY_BYTES + 1)


transport = default_transport


# ---------------------------------------------------------------- validation

def validate_manifest(doc) -> str | None:
    """Minimal structural check of asaa.service-manifest.v1 (the runtime does not depend on a JSON Schema library)."""
    if not isinstance(doc, dict):
        return "manifest is not an object"
    if set(doc) - _MANIFEST_KEYS:
        return "manifest has unknown fields"
    if _MANIFEST_REQUIRED - set(doc):
        return "manifest is missing required fields"
    if doc["schema"] != "asaa.service-manifest.v1":
        return "unsupported manifest schema"
    if not isinstance(doc["service"], str) or not _SERVICE.match(doc["service"]):
        return "invalid service id"
    if doc["project"] not in PROJECTS:
        return "invalid project"
    if not isinstance(doc["version"], str) or len(doc["version"]) > 64:
        return "invalid version"
    if doc.get("commit") is not None and not (isinstance(doc["commit"], str) and _COMMIT.match(doc["commit"])):
        return "invalid commit"
    if "environment" in doc and doc["environment"] not in {"development", "test", "staging", "production", "local-prod"}:
        return "invalid environment"
    if doc["status"] not in STATES:
        return "invalid status"
    if not isinstance(doc["checkedAt"], str):
        return "invalid checkedAt"
    try:
        datetime.fromisoformat(doc["checkedAt"].replace("Z", "+00:00"))
    except ValueError:
        return "invalid checkedAt"
    checks = doc["checks"]
    if not isinstance(checks, dict) or any(v not in STATES | {"disabled"} for v in checks.values()):
        return "invalid checks"
    caps = doc["capabilities"]
    if not isinstance(caps, list) or len(set(map(str, caps))) != len(caps) or not all(isinstance(c, str) and _CAPABILITY.match(c) for c in caps):
        return "invalid capabilities"
    contracts = doc.get("contracts", {})
    if not isinstance(contracts, dict) or not all(isinstance(v, str) and _CONTRACT_VERSION.match(v) for v in contracts.values()):
        return "invalid contracts"
    return None


# ---------------------------------------------------------------- probing

def _result(service: dict, project: str, status: str, detail: str | None = None, version=None, commit=None) -> dict:
    row = {"service": service["service"], "project": project, "status": status, "version": version, "commit": commit, "checkedAt": _stamp()}
    if detail:
        row["detail"] = detail
    return row


def probe(project: str, service: dict, allowed_hosts: list[str]) -> dict:
    """Never raises: every failure mode maps to a status."""
    try:
        if service["service"] == SERVICE_ID:  # this process: no HTTP round-trip to ourselves
            manifest = build_manifest()
            return _result(service, project, manifest["status"], None, manifest["version"], manifest["commit"])
        base = base_url_for(service)
        if not base:
            return _result(service, project, "invalid", "no base URL configured")
        manifest_mode = bool(service.get("manifestPath"))
        url = base.rstrip("/") + (service["manifestPath"] if manifest_mode else service["healthPath"])
        if not url_allowed(url, allowed_hosts):
            return _result(service, project, "invalid", "base URL is not loopback or allowlisted")
        try:
            code, body = transport(url, PROBE_TIMEOUT_SECONDS)
        except (OSError, TimeoutError, urllib.error.URLError, ValueError):
            return _result(service, project, "unreachable", "no response")
        if len(body) > MAX_BODY_BYTES:
            return _result(service, project, "invalid", "response too large")
        try:
            doc = json.loads(body.decode("utf-8")) if body else None
        except ValueError:
            doc = None
        if manifest_mode:
            if doc is None and not (200 <= code < 300):
                return _result(service, project, "down", f"HTTP {code}")
            problem = validate_manifest(doc)
            if problem:
                return _result(service, project, "invalid", problem)
            if doc["service"] != service["service"] or doc["project"] != project:
                return _result(service, project, "invalid", "manifest identity does not match the registry")
            return _result(service, project, doc["status"], None, doc["version"], doc.get("commit"))
        # healthPath: liveness only. HTTP 2xx with a JSON status of "ok" is up; anything else is down. No version or commit is reported.
        if 200 <= code < 300 and isinstance(doc, dict) and doc.get("status") == "ok":
            return _result(service, project, "ok")
        return _result(service, project, "down", f"HTTP {code}" if not 200 <= code < 300 else "health status is not ok")
    except Exception:  # noqa: BLE001 - standalone rule: a broken probe must not break the endpoint
        return _result(service, project, "invalid", "probe error")



def collect() -> dict:
    registry, reason = load_registry()
    if registry is None:
        return {"checkedAt": _stamp(), "registry": {"loaded": False, "reason": reason}, "services": []}
    allowed = list(get_settings().ecosystem_allowed_hosts)
    targets = []
    skipped = []
    for project in registry["projects"]:
        code = project.get("code") if isinstance(project, dict) else None
        if code not in PROJECTS:
            continue
        for service in project.get("services", []):
            if not (isinstance(service, dict) and isinstance(service.get("service"), str)):
                continue
            if service.get("manifestPath") or service.get("healthPath"):
                targets.append((code, service))
            else:  # portals and web UIs: listed, never probed
                skipped.append((code, service))
    with ThreadPoolExecutor(max_workers=max(1, min(8, len(targets)))) as pool:
        services = list(pool.map(lambda item: probe(item[0], item[1], allowed), targets))
    services += [_result(service, code, "not-probed") for code, service in skipped]
    return {"checkedAt": _stamp(), "registry": {"loaded": True, "orgId": registry.get("orgId"), "contracts": registry.get("contracts", {})},
            "services": services}


def cached_collect() -> dict:
    with _cache_lock:
        hit = _cache.get("status")
        if hit and _now() - hit[0] < CACHE_TTL_SECONDS:
            return hit[1]
    result = collect()
    with _cache_lock:
        _cache["status"] = (_now(), result)
    return result


@router.get("/api/v1/operations/ecosystem")
def ecosystem_status(principal: Annotated[Principal, Depends(require_permission("ops:ecosystem:read"))]):
    return cached_collect()
