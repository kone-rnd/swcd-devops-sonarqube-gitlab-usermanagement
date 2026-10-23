#!/usr/bin/env python3
import argparse
import base64
import json
import os
import sys
from collections import Counter

import requests

HOST = (os.environ.get("SONAR_HOST") or os.environ.get("SONARQUBE_HOST") or "").rstrip("/")
TOKEN = os.environ.get("SONAR_TOKEN") or os.environ.get("SONARQUBE_TOKEN") or ""
AUTH = "Basic " + base64.b64encode(f"{TOKEN}:".encode()).decode()


def get(path, params):
    try:
        r = requests.get(f"{HOST}/{path}", params=params, headers={"Authorization": AUTH}, timeout=60)
        r.raise_for_status()
        return r.json()
    except requests.HTTPError as e:
        print(f"  HTTP {e.response.status_code} on {path}: {e.response.text[:200]}", file=sys.stderr)
        return None
    except requests.RequestException as e:
        print(f"  request error on {path}: {e}", file=sys.stderr)
        return None


def all_users():
    users, page = [], 1
    while True:
        d = get("api/users/search", {"ps": 500, "p": page})
        if not d:
            break
        batch = d.get("users", [])
        users += batch
        total = d.get("paging", {}).get("total", d.get("total", 0))
        if not batch or page * 500 >= total:
            break
        page += 1
    return users


def main():
    ap = argparse.ArgumentParser(description="Export SAML email -> login map from SonarQube.")
    ap.add_argument("--provider", default="saml", help="externalProvider to keep (default: saml).")
    ap.add_argument("-o", "--output", default="sonar-saml-users.json")
    ap.add_argument("--debug", action="store_true", help="Print a sample raw user record.")
    args = ap.parse_args()

    if not HOST or not TOKEN:
        sys.exit("error: set SONAR_HOST and SONAR_TOKEN (admin token)")

    users = all_users()
    print(f"host: {HOST}  fetched users: {len(users)}")
    if not users:
        sys.exit("no users returned — check SONAR_HOST, token validity, and connectivity")

    if args.debug:
        sample = dict(users[0])
        sample["email"] = "<redacted>" if sample.get("email") else sample.get("email")
        print("sample user record:\n" + json.dumps(sample, indent=2))

    breakdown = Counter(u.get("externalProvider") or ("local" if u.get("local") else "none") for u in users)
    print(f"externalProvider breakdown: {dict(breakdown)}")

    if not any("externalProvider" in u for u in users):
        print("WARNING: no 'externalProvider' field on any user — your token likely lacks "
              "'Administer System'. SonarQube only returns provider/email to an admin token.", file=sys.stderr)

    mapping, dupes = {}, 0
    for u in users:
        if u.get("externalProvider") != args.provider:
            continue
        # SAML accounts expose the corporate email as externalIdentity (the SAML
        # NameID), often with an empty email field, so fall back to it.
        key = (u.get("email") or u.get("externalIdentity") or "").lower()
        if not key:
            continue
        if key in mapping:
            dupes += 1
            print(f"  warn: duplicate {args.provider} identity {key} ({mapping[key]} kept, {u['login']} ignored)", file=sys.stderr)
            continue
        mapping[key] = u["login"]

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(mapping, f, indent=2, ensure_ascii=False, sort_keys=True)
    print(f"wrote {args.output}: {len(mapping)} '{args.provider}' users ({dupes} duplicate emails skipped)")
    if not mapping:
        print(f"NOTE: 0 matched. Pick the right value from the breakdown above and re-run with "
              f"--provider <name> (seen: {sorted(breakdown)}).", file=sys.stderr)


if __name__ == "__main__":
    main()
