from __future__ import annotations

from importlib import metadata
from pathlib import Path
import json
import re
from urllib.parse import quote
from urllib.request import Request, urlopen

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.core.cache import cache
from django.http import Http404, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

_REQUIREMENTS_PATH = Path(__file__).resolve().parents[1] / "requirements.txt"
_LATEST_CACHE_TTL = 60 * 60 * 12
_LATEST_FAILURE_CACHE_TTL = 60 * 10
_LATEST_UNAVAILABLE = "__PAXALIA_DEPENDENCY_UNAVAILABLE__"
_LATEST_CACHE_PREFIX = "paxalia-dashboard:dependency-latest:"
_RUNTIME_CACHE_KEY = "paxalia-dashboard:dependency-runtime-v2"
_RUNTIME_CACHE_TTL = 60 * 10


def _normalize_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _parse_requirement(line: str):
    """Parse a requirements line while safely ignoring decorated comments/separators."""
    line = line.lstrip("\ufeff").strip()
    if not line:
        return None

    # Supports headings/separators such as ----, ====, ####, ********, etc.
    if line.startswith("#") or re.fullmatch(r"[-_=#*~.`:;\s]+", line):
        return None

    # pip include/constraint/editable/options are not package declarations here.
    if line.startswith((
        "-r ", "-c ", "-e ",
        "--requirement", "--constraint", "--editable", "--index-url",
        "--extra-index-url", "--find-links", "--trusted-host", "--hash",
        "--only-binary", "--no-binary", "--prefer-binary", "--pre",
    )):
        return None

    # Remove an ordinary inline comment. Hashes inside URLs are left alone.
    line = re.sub(r"\s+#.*$", "", line).strip()
    if not line:
        return None

    try:
        from packaging.requirements import Requirement
        req = Requirement(line)
        # requirements.txt normally contains no environment marker, but when it
        # does, include only the requirement applicable to this environment.
        if req.marker is not None and not req.marker.evaluate():
            return None
        return req.name, str(req.specifier) or "any"
    except Exception:
        match = re.match(r"^([A-Za-z0-9][A-Za-z0-9_.-]*)(?:\s*)(.*)$", line)
        if not match:
            return None
        name, rest = match.groups()
        if rest and not re.match(r"^[<>=!~;,+*\s\[\]().-]", rest):
            return None
        return name, rest.strip() or "any"


def _declared_requirements():
    rows = {}
    if not _REQUIREMENTS_PATH.exists():
        return rows
    for line in _REQUIREMENTS_PATH.read_text(encoding="utf-8").splitlines():
        item = _parse_requirement(line)
        if not item:
            continue
        name, specifier = item
        rows[_normalize_name(name)] = {"name": name, "specifier": specifier}
    return rows


def _distribution_index():
    result = {}
    for dist in metadata.distributions():
        name = dist.metadata.get("Name") or dist.name
        if name:
            result[_normalize_name(name)] = dist
    return result


def _parse_metadata_requirement(value: str):
    try:
        from packaging.requirements import Requirement
        req = Requirement(value)
        if req.marker is not None and not req.marker.evaluate():
            return None
        return req.name, str(req.specifier) or "any"
    except Exception:
        match = re.match(r"^([A-Za-z0-9][A-Za-z0-9_.-]*)(.*)$", value.strip())
        if not match:
            return None
        return match.group(1), match.group(2).strip() or "any"


def _compute_runtime_dependencies():
    """Return the complete runtime dependency closure for Paxalia Dashboard."""
    declared = _declared_requirements()
    dists = _distribution_index()

    root = dists.get(_normalize_name("paxalia-dashboard"))
    queue = []
    if root:
        for requirement in root.requires or []:
            parsed = _parse_metadata_requirement(requirement)
            if parsed:
                queue.append((parsed[0], True, declared.get(_normalize_name(parsed[0]), {}).get("specifier", parsed[1])))
    else:
        queue.extend(
            (item["name"], True, item["specifier"])
            for item in declared.values()
        )

    rows = {}
    seen = set()
    while queue:
        name, direct, specifier = queue.pop(0)
        key = _normalize_name(name)
        if key in seen or key == _normalize_name("paxalia-dashboard"):
            continue
        seen.add(key)

        dist = dists.get(key)
        declared_item = declared.get(key)
        rows[key] = {
            "name": (declared_item or {}).get("name") or (dist.metadata.get("Name") if dist else None) or name,
            "specifier": (declared_item or {}).get("specifier") or specifier or "any",
            "installed": dist.version if dist else None,
            "source": "direct" if direct else "transitive",
        }

        if dist:
            for requirement in dist.requires or []:
                parsed = _parse_metadata_requirement(requirement)
                if parsed:
                    child, child_specifier = parsed
                    queue.append((child, False, child_specifier))

    for key, item in declared.items():
        if key not in rows:
            dist = dists.get(key)
            rows[key] = {
                "name": item["name"],
                "specifier": item["specifier"],
                "installed": dist.version if dist else None,
                "source": "direct",
            }

    return sorted(rows.values(), key=lambda row: row["name"].lower())


def _runtime_dependencies():
    cached = cache.get(_RUNTIME_CACHE_KEY)
    if cached is not None:
        return cached
    rows = _compute_runtime_dependencies()
    cache.set(_RUNTIME_CACHE_KEY, rows, _RUNTIME_CACHE_TTL)
    return rows


def _version_key(value: str):
    if not value:
        return ()
    try:
        from packaging.version import Version
        return (Version(value),)
    except Exception:
        return tuple((0, int(x)) if x.isdigit() else (1, x.lower()) for x in re.split(r"[.+-]", value))


def _latest(name: str):
    key = _LATEST_CACHE_PREFIX + _normalize_name(name)
    cached = cache.get(key)
    if cached is not None:
        return None if cached == _LATEST_UNAVAILABLE else cached

    url = f"https://pypi.org/pypi/{quote(name, safe='')}/json"
    try:
        req = Request(
            url,
            headers={
                "User-Agent": "paxalia-dashboard/3.0.0 dependency-health",
                "Accept": "application/json",
            },
        )
        with urlopen(req, timeout=4) as response:
            if getattr(response, "status", 200) != 200:
                raise OSError(f"PyPI returned HTTP {response.status}")
            payload = json.loads(response.read().decode("utf-8"))

        version = payload.get("info", {}).get("version")
        if not version:
            cache.set(key, _LATEST_UNAVAILABLE, _LATEST_FAILURE_CACHE_TTL)
            return None

        cache.set(key, version, _LATEST_CACHE_TTL)
        return version
    except Exception:
        # Cache failures briefly so an unreachable PyPI does not cause every
        # package to pay the full network timeout on every page refresh.
        cache.set(key, _LATEST_UNAVAILABLE, _LATEST_FAILURE_CACHE_TTL)
        return None


@staff_member_required
def dependencies(request):
    sidebar = (getattr(settings, "PAXALIA_DASHBOARD", {}) or {}).get("SIDEBAR_SECTIONS", [])
    if "security" not in sidebar:
        raise Http404

    rows = _runtime_dependencies()
    return render(
        request,
        "paxalia/dependencies.html",
        {
            "active_page": "dependencies",
            "page_title": "Dependencies",
            "page_subtitle": "Complete runtime dependency inventory and upstream release status",
            "dependencies": rows,
            "package_count": len(rows),
            "direct_count": sum(row["source"] == "direct" for row in rows),
            "transitive_count": sum(row["source"] == "transitive" for row in rows),
        },
    )


@staff_member_required
@require_GET
def dependency_status(request, package_name: str):
    key = _normalize_name(package_name)
    row = next((item for item in _runtime_dependencies() if _normalize_name(item["name"]) == key), None)
    if row is None:
        return JsonResponse({"error": "Package is not part of the Paxalia Dashboard runtime dependency set."}, status=404)

    latest = _latest(row["name"])
    installed = row["installed"]
    if not installed:
        status = "missing"
    elif not latest:
        status = "unavailable"
    else:
        status = "update" if _version_key(latest) > _version_key(installed) else "current"

    return JsonResponse({
        "name": row["name"],
        "installed": installed or "Not installed",
        "latest": latest,
        "source": "PyPI",
        "source_url": f"https://pypi.org/project/{quote(row['name'], safe='-_.')}/",
        "status": status,
        "source_status": "ok" if latest else "unavailable",
    })
