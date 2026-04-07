"""Ultimate Guitar search/download using curl_cffi for TLS fingerprint impersonation.

Cloudflare blocks requests based on TLS fingerprinting (JA3/JA4).
curl_cffi impersonates real browser TLS handshakes, bypassing detection.
"""

import html as html_module
import json
import re
import base64
from typing import Any
from urllib.parse import quote

from curl_cffi import requests


def _extract_store(page_html: str) -> dict[str, Any]:
    match = re.search(r'class="js-store"\s+data-content="([^"]*)"', page_html)
    if not match:
        return {}
    return json.loads(html_module.unescape(match.group(1)))


def search(query: str) -> list[dict[str, Any]]:
    """Search Ultimate Guitar for Guitar Pro tabs."""
    url = f"https://www.ultimate-guitar.com/search.php?search_type=title&value={quote(query)}&type[]=500"
    resp = requests.get(url, impersonate="chrome", timeout=30)
    resp.raise_for_status()

    store = _extract_store(resp.text)
    results = store.get("store", {}).get("page", {}).get("data", {}).get("results", [])
    tabs: list[dict[str, Any]] = []
    for item in results:
        if not isinstance(item, dict):
            continue
        tab_url = item.get("tab_url", "")
        if not tab_url or "/pro/" in tab_url:
            continue
        tabs.append({
            "id": item.get("id"),
            "song_name": item.get("song_name", ""),
            "artist_name": item.get("artist_name", ""),
            "rating": round(float(item.get("rating") or 0), 1),
            "votes": item.get("votes", 0),
            "tab_url": tab_url,
        })
    return tabs


def download(tab_url: str) -> dict[str, Any]:
    """Download a Guitar Pro file from Ultimate Guitar."""
    resp = requests.get(tab_url, impersonate="chrome", timeout=30)
    resp.raise_for_status()

    store = _extract_store(resp.text)
    page_data = store.get("store", {}).get("page", {}).get("data", {})

    tab_view = page_data.get("tab_view", {})
    binary_id = tab_view.get("binary_id", "")
    if not binary_id:
        raise ValueError("Could not find download token on this page")

    download_url = f"https://tabs.ultimate-guitar.com/download/public/{binary_id}"
    dl_resp = requests.get(download_url, impersonate="chrome", timeout=30,
                           headers={"Referer": tab_url})
    dl_resp.raise_for_status()

    if len(dl_resp.content) < 50:
        raise ValueError("Downloaded file is too small / empty")

    tab = page_data.get("tab", {})
    artist = tab.get("artist_name", "Unknown")
    song = tab.get("song_name", "Unknown")

    ext = ".gp"
    meta = tab_view.get("meta", {})
    file_ext = meta.get("fileExtension", "")
    if file_ext and file_ext.startswith("."):
        ext = file_ext

    filename = f"{artist} - {song}{ext}"
    return {
        "filename": filename,
        "data_base64": base64.b64encode(dl_resp.content).decode(),
        "size": len(dl_resp.content),
    }
