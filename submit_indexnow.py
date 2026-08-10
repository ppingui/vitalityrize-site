#!/usr/bin/env python3
"""Ping IndexNow with the site's URLs so Bing (and therefore ChatGPT's retrieval)
picks up changes immediately instead of waiting for a crawl.

    python3 submit_indexnow.py              # every URL in sitemap.xml
    python3 submit_indexnow.py /about/ /support/   # just these paths

Run it after `python3 build.py` and after the push has actually deployed —
IndexNow fetches the URLs, so submitting before deploy just wastes the ping.
"""

from __future__ import annotations

import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent
SITE = "https://www.vitalityrize.me"
HOST = "www.vitalityrize.me"
KEY = "5662c5be19cfec89bc8ef3c0d2465bb0"
ENDPOINT = "https://api.indexnow.org/IndexNow"


def sitemap_urls() -> list[str]:
    xml = (ROOT / "sitemap.xml").read_text(encoding="utf-8")
    return re.findall(r"<loc>([^<]+)</loc>", xml)


def main() -> int:
    args = sys.argv[1:]
    urls = [SITE.rstrip("/") + a if a.startswith("/") else a for a in args] \
        or sitemap_urls()

    # The key file must be live before any submission will validate.
    key_url = f"{SITE}/{KEY}.txt"
    try:
        with urllib.request.urlopen(key_url, timeout=15) as r:
            served = r.read().decode().strip()
    except Exception as exc:
        print(f"! cannot fetch {key_url}: {exc}")
        return 1
    if served != KEY:
        print(f"! {key_url} serves {served!r}, expected {KEY!r}")
        return 1
    print(f"key file OK at {key_url}")

    payload = json.dumps({
        "host": HOST,
        "key": KEY,
        "keyLocation": key_url,
        "urlList": urls,
    }).encode()

    req = urllib.request.Request(
        ENDPOINT, data=payload,
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            print(f"IndexNow {r.status} {r.reason} for {len(urls)} URLs")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")[:400]
        print(f"IndexNow {exc.code} {exc.reason}: {body}")
        # 403 = key not valid for this host; 422 = URLs don't match host/key.
        return 1
    for u in urls:
        print(f"  {u}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
