"""Optional online fallback: resolve a part's category from a distributor API.

This is the layer that mops up the long tail — parts whose category the offline
rules in ``bom.py`` can't guess (a bare, unfamiliar part number with no useful
description). It is OFF by default and the rest of the app never depends on it:

  * It does nothing unless the ``MOUSER_API_KEY`` environment variable is set.
    Get a free key at https://www.mouser.com/api-hub/ , then set it on the
    container (e.g. in the systemd unit:  Environment=MOUSER_API_KEY=...) and
    restart the service.
  * Every successful answer is cached to ``data/part_category_cache.json`` so a
    given part number is fetched at most once, the app stays fast, and lookups
    keep working even when the internet (or Mouser) is down.
  * Any failure — no key, network down, timeout, unexpected response, rate
    limit — returns ``None`` quietly. The caller just keeps the offline guess.

Why Mouser: a free key, and its part-number search returns a "Category" string
directly, so we don't have to scrape datasheets. Swapping in DigiKey/Octopart
later means only changing ``_query_provider`` and ``_map_category``.
"""

import json
import os
import urllib.error
import urllib.request

import categories
import db

API_KEY = os.environ.get("MOUSER_API_KEY", "").strip()
ENABLED = bool(API_KEY)

_ENDPOINT = "https://api.mouser.com/api/v1/search/partnumber?apiKey=" + API_KEY
_TIMEOUT = 6  # seconds — never let a slow API stall an import
_CACHE_PATH = os.path.join(os.path.dirname(db.DB_PATH), "part_category_cache.json")

def _load_cache():
    try:
        with open(_CACHE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _save_cache(cache):
    try:
        os.makedirs(os.path.dirname(_CACHE_PATH), exist_ok=True)
        with open(_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=0)
    except OSError:
        pass  # a cache we can't write is not worth crashing an import over


def _map_category(text):
    """Turn Mouser's category text ("Linear Voltage Regulators") into one of our
    categories. The offline keyword rules already know how to read descriptive
    text like this, so they do the work here too — one set of rules to maintain,
    and an online answer can never invent a category name the tabs don't know."""
    if not text:
        return None
    cat = categories.guess_category(text)
    return None if cat == categories.UNCATEGORIZED else cat


def _query_provider(part_number):
    """Ask Mouser for the part's category text, or None on any problem."""
    body = json.dumps({
        "SearchByPartRequest": {
            "mouserPartNumber": part_number,
            "partSearchOptions": "Exact",
        }
    }).encode("utf-8")
    req = urllib.request.Request(
        _ENDPOINT, data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, ValueError, TimeoutError, OSError):
        return None
    try:
        parts = data["SearchResults"]["Parts"]
    except (KeyError, TypeError):
        return None
    for part in parts or []:
        cat = part.get("Category")
        if cat:
            return cat
    return None


def lookup_category(part_number):
    """Return our category for ``part_number`` via the online provider, or None.

    Safe to call always: returns None instantly when disabled. Caches every
    answer (including "not found", stored as "") so we never re-fetch."""
    if not ENABLED:
        return None
    key = (part_number or "").strip().upper()
    if not key:
        return None

    cache = _load_cache()
    if key in cache:
        return cache[key] or None

    cat = _map_category(_query_provider(key))
    cache[key] = cat or ""
    _save_cache(cache)
    return cat
