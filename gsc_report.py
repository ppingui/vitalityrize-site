#!/usr/bin/env python3
"""Pull Search Console data for vitalityrize.me and surface actionable buckets.

Copied from pixelislands-site/gsc_report.py; the property, the locale set and a
--list-sites mode are the only differences. Same credential files, so once one
site is authorised the other works without a second consent.

Usage:
    python3 gsc_report.py                      # last 28 days, quick-wins report
    python3 gsc_report.py --days 90
    python3 gsc_report.py --raw queries        # dump top queries as TSV
    python3 gsc_report.py --raw pages
    python3 gsc_report.py --list-sites         # every property the credential can read
    python3 gsc_report.py --site sc-domain:example.com

Auth, in order of preference:

1. OAuth desktop-app credentials (default). Put the client JSON downloaded from Google
   Cloud at ~/.gsc-oauth-client.json. The first run opens a browser once; the refresh
   token is cached at ~/.gsc-token.json and reused silently after that. You authorise as
   yourself, so no extra Search Console user needs to be added.
2. A service-account JSON key at ~/.gsc-service-account.json, whose client_email has been
   added as a user on the property.

Both paths keep credentials OUTSIDE this repo. Never commit them.

No third-party HTTP/Google libraries: signs the service-account JWT with `cryptography`
and talks to the REST API over urllib.
"""
import argparse
import base64
import datetime as dt
import hashlib
import json
import os
import pathlib
import secrets
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from collections import defaultdict
from http.server import BaseHTTPRequestHandler, HTTPServer

SITE = "sc-domain:vitalityrize.me"
TOKEN_URL = "https://oauth2.googleapis.com/token"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
API = "https://searchconsole.googleapis.com/webmasters/v3/sites/{site}/searchAnalytics/query"
SITES_API = "https://searchconsole.googleapis.com/webmasters/v3/sites"
SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"
DEFAULT_KEY = pathlib.Path.home() / ".gsc-service-account.json"
CLIENT_FILE = pathlib.Path.home() / ".gsc-oauth-client.json"
TOKEN_FILE = pathlib.Path.home() / ".gsc-token.json"


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _post_form(url: str, params: dict) -> dict:
    body = urllib.parse.urlencode(params).encode()
    with urllib.request.urlopen(urllib.request.Request(url, data=body), timeout=30) as r:
        return json.load(r)


def _write_private(path: pathlib.Path, data: dict) -> None:
    """Write 0600 from the start — never let the token exist world-readable, even briefly."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as fh:
        json.dump(data, fh)


def _client_config() -> tuple:
    if not CLIENT_FILE.exists():
        sys.exit(
            f"No OAuth client at {CLIENT_FILE}\n"
            f"In Google Cloud → APIs & Services → Credentials → Create credentials →\n"
            f"OAuth client ID → Desktop app, download the JSON, and save it there.")
    data = json.loads(CLIENT_FILE.read_text())
    cfg = data.get("installed") or data.get("web")
    if not cfg or "client_id" not in cfg:
        sys.exit(f"{CLIENT_FILE} is not an OAuth client file (expected an 'installed' key).")
    return cfg["client_id"], cfg.get("client_secret", "")


def _authorise(client_id: str, client_secret: str) -> dict:
    """One-time browser consent over a loopback redirect, with PKCE."""
    verifier = secrets.token_urlsafe(64)
    challenge = _b64(hashlib.sha256(verifier.encode()).digest())
    state = secrets.token_urlsafe(16)
    got = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            got.update({k: v[0] for k, v in
                        urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).items()})
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            ok = "code" in got
            self.wfile.write(
                f"<h2>{'Authorised — you can close this tab.' if ok else 'Authorisation failed.'}</h2>"
                .encode())

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 0), Handler)
    redirect = f"http://127.0.0.1:{srv.server_address[1]}"
    url = f"{AUTH_URL}?" + urllib.parse.urlencode({
        "client_id": client_id, "redirect_uri": redirect, "response_type": "code",
        "scope": SCOPE, "access_type": "offline", "prompt": "consent",
        "code_challenge": challenge, "code_challenge_method": "S256", "state": state})

    print("Opening your browser to authorise read-only Search Console access.")
    print(f"If it does not open, visit:\n{url}\n")
    webbrowser.open(url)
    srv.handle_request()
    srv.server_close()

    if got.get("state") != state:
        sys.exit("OAuth state mismatch — aborted.")
    if "code" not in got:
        sys.exit(f"OAuth failed: {got.get('error', got)}")

    tok = _post_form(TOKEN_URL, {
        "client_id": client_id, "client_secret": client_secret, "code": got["code"],
        "code_verifier": verifier, "grant_type": "authorization_code",
        "redirect_uri": redirect})
    if "refresh_token" not in tok:
        sys.exit("Google returned no refresh token. Revoke the app at "
                 "https://myaccount.google.com/permissions and run again.")
    return tok


def oauth_token() -> str:
    client_id, client_secret = _client_config()

    if TOKEN_FILE.exists():
        saved = json.loads(TOKEN_FILE.read_text())
        try:
            tok = _post_form(TOKEN_URL, {
                "client_id": client_id, "client_secret": client_secret,
                "refresh_token": saved["refresh_token"], "grant_type": "refresh_token"})
            return tok["access_token"]
        except urllib.error.HTTPError as e:
            if e.code not in (400, 401):
                raise
            # Refresh tokens die if revoked, unused for six months, or issued while the
            # consent screen was still in Testing. Fall through to a fresh consent.
            print("Saved credential rejected — re-authorising.", file=sys.stderr)

    tok = _authorise(client_id, client_secret)
    _write_private(TOKEN_FILE, {"refresh_token": tok["refresh_token"]})
    print(f"Saved refresh token to {TOKEN_FILE} (0600).")
    return tok["access_token"]


def service_account_token(key_path: pathlib.Path) -> str:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding

    sa = json.loads(key_path.read_text())
    now = int(time.time())
    header = {"alg": "RS256", "typ": "JWT"}
    claims = {"iss": sa["client_email"], "scope": SCOPE, "aud": TOKEN_URL,
              "iat": now, "exp": now + 3600}
    signing_input = f"{_b64(json.dumps(header).encode())}.{_b64(json.dumps(claims).encode())}".encode()
    key = serialization.load_pem_private_key(sa["private_key"].encode(), password=None)
    sig = key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
    assertion = f"{signing_input.decode()}.{_b64(sig)}"

    body = urllib.parse.urlencode({
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "assertion": assertion}).encode()
    with urllib.request.urlopen(urllib.request.Request(TOKEN_URL, data=body), timeout=30) as r:
        return json.load(r)["access_token"]


def query(token, start, end, dimensions, row_limit=1000, dimension_filters=None):
    payload = {"startDate": start, "endDate": end, "dimensions": dimensions,
               "rowLimit": row_limit, "dataState": "final"}
    if dimension_filters:
        payload["dimensionFilterGroups"] = [{"filters": dimension_filters}]
    req = urllib.request.Request(
        API.format(site=urllib.parse.quote(SITE, safe="")),
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r).get("rows", [])


def fmt(rows, dims):
    out = []
    for r in rows:
        d = dict(zip(dims, r["keys"]))
        d.update(clicks=r["clicks"], impressions=r["impressions"],
                 ctr=r["ctr"] * 100, position=r["position"])
        out.append(d)
    return out


LOCALES = {"de", "es", "fr", "pt", "ja"}


def canonical_path(url: str) -> tuple:
    """Reduce a GSC page URL to (logical path, locale).

    Drops the origin, any #fragment and any ?query, then lifts a locale prefix off
    the front, so /de/x/, /x/ and /x/#faq all reduce to the same logical page and
    differ only by locale.
    """
    path = urllib.parse.urlsplit(url).path or "/"
    parts = [p for p in path.split("/") if p]
    if parts and parts[0] in LOCALES:
        return "/" + "/".join(parts[1:]) + ("/" if len(parts) > 1 else ""), parts[0]
    return path, "en"


def quick_wins(token, start, end):
    """The buckets that actually suggest an action."""
    q = fmt(query(token, start, end, ["query"]), ["query"])
    qp = fmt(query(token, start, end, ["query", "page"]), ["query", "page"])

    striking = [r for r in q if 5 <= r["position"] <= 15 and r["impressions"] >= 20]
    low_ctr = [r for r in q if r["impressions"] >= 50 and r["ctr"] < 3]
    page2 = [r for r in q if 11 <= r["position"] <= 20 and r["impressions"] >= 10]

    # Raw GSC page strings overstate cannibalization badly. Anchor links Google
    # generates into homepage sections (/#faq, /#features) arrive as separate URLs,
    # and a translated page ranking in its own language is the hreflang mesh working,
    # not two pages fighting. Collapse both before deciding anything is wrong.
    by_query = defaultdict(set)
    for r in qp:
        by_query[r["query"]].add(canonical_path(r["page"]))

    cannibal, cross_locale = {}, {}
    for kq, pairs in by_query.items():
        paths = {p for p, _ in pairs}
        if len(paths) > 1:
            cannibal[kq] = paths
        elif len({loc for _, loc in pairs}) > 1:
            cross_locale[kq] = (next(iter(paths)), sorted(loc for _, loc in pairs))

    def table(title, rows, note):
        print(f"\n{title}  ({len(rows)})")
        print(f"  {note}")
        if not rows:
            print("    — nothing yet")
            return
        rows = sorted(rows, key=lambda r: -r["impressions"])[:15]
        print(f"    {'query':<44} {'pos':>6} {'impr':>7} {'clicks':>7} {'ctr':>7}")
        for r in rows:
            print(f"    {r['query'][:44]:<44} {r['position']:>6.1f} "
                  f"{r['impressions']:>7.0f} {r['clicks']:>7.0f} {r['ctr']:>6.1f}%")

    tot_i = sum(r["impressions"] for r in q)
    tot_c = sum(r["clicks"] for r in q)
    print(f"=== {SITE} — Search Console {start} → {end} ===")
    print(f"  {len(q)} queries | {tot_i:.0f} impressions | {tot_c:.0f} clicks "
          f"| {100*tot_c/tot_i if tot_i else 0:.1f}% CTR")

    table("A. STRIKING DISTANCE", striking,
          "pos 5-15 with real impressions — small on-page edits can move these to page 1 top")
    table("B. LOW CTR", low_ctr,
          "ranking but not clicked — rewrite <title> and meta description")
    table("C. PAGE TWO", page2,
          "pos 11-20 — expand the content or add internal links")

    print(f"\nD. CANNIBALIZATION  ({len(cannibal)})")
    print("  one query, genuinely different pages competing — fragments and")
    print("  translations already collapsed, so these are real overlaps")
    if not cannibal:
        print("    — none")
    else:
        for kq, paths in sorted(cannibal.items(), key=lambda x: -len(x[1]))[:10]:
            print(f"    {kq[:50]}")
            for p in sorted(paths):
                print(f"        {p}")

    print(f"\nE. CROSS-LOCALE OVERLAP  ({len(cross_locale)})")
    print("  same page, several languages ranking for one query — usually fine,")
    print("  but check hreflang if the wrong language is winning")
    if not cross_locale:
        print("    — none")
    else:
        for kq, (path, locs) in sorted(cross_locale.items(), key=lambda x: -len(x[1][1]))[:10]:
            print(f"    {kq[:50]}")
            print(f"        {path}  [{', '.join(locs)}]")


def main():
    global SITE
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=28)
    ap.add_argument("--key", type=pathlib.Path, default=DEFAULT_KEY)
    ap.add_argument("--raw", choices=["queries", "pages", "countries"])
    ap.add_argument("--site", default=SITE, help=f"Search Console property (default {SITE})")
    ap.add_argument("--list-sites", action="store_true",
                    help="list every property the credential can read, then exit")
    ap.add_argument("--reauth", action="store_true",
                    help="discard the cached token and run the consent flow again")
    a = ap.parse_args()
    SITE = a.site

    if a.reauth:
        TOKEN_FILE.unlink(missing_ok=True)

    # GSC finalizes data with ~2-3 days lag; ending today would show a misleading dip.
    end = dt.date.today() - dt.timedelta(days=3)
    start = end - dt.timedelta(days=a.days)

    # Prefer a service-account key only if one was deliberately placed; otherwise OAuth.
    token = service_account_token(a.key) if a.key.exists() else oauth_token()

    if a.list_sites:
        req = urllib.request.Request(SITES_API, headers={"Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(req, timeout=30) as r:
            for site in json.load(r).get("siteEntry", []):
                print(f"{site['permissionLevel']:<22} {site['siteUrl']}")
        return

    if a.raw:
        dims = {"queries": ["query"], "pages": ["page"], "countries": ["country"]}[a.raw]
        rows = fmt(query(token, str(start), str(end), dims), dims)
        rows.sort(key=lambda r: -r["impressions"])
        print("\t".join(dims + ["clicks", "impressions", "ctr", "position"]))
        for r in rows:
            print("\t".join([str(r[d]) for d in dims] +
                            [f"{r['clicks']:.0f}", f"{r['impressions']:.0f}",
                             f"{r['ctr']:.2f}", f"{r['position']:.1f}"]))
    else:
        quick_wins(token, str(start), str(end))


if __name__ == "__main__":
    main()
