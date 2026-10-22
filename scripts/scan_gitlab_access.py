#!/usr/bin/env python3
"""Scan a GitLab (SaaS) group tree and export a scope-centric access map.

Walks the root group plus all nested subgroups and projects, then emits, per scope
(group or project), the direct members grouped by access level — plus a single
user_details catalog. Scopes carry real GitLab id and parent_id, so inherited
access is resolvable by walking parent_id.

Output (user.json shape):
[
  {
    "user_details": {
      "<user_id>": {"name": "...", "username": "...", "email": "..."}
    },
    "scope_details": [
      {
        "scope": "<full_path>",
        "id": 123,
        "parent_id": 100,
        "access_details": {
          "Owner":      [<user_id>, ...],
          "Maintainer": [<user_id>, ...],
          "Developer":  [<user_id>, ...]
        }
      }
    ]
  }
]

Auth: set TF_VAR_gitlab_token (or GITLAB_TOKEN) to an admin/owner token with api scope.
Optional: GITLAB_HOST (default https://gitlab.com).
"""
import argparse
import json
import os
import sys
import time
import re
import urllib.parse
from collections import defaultdict

import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

ACCESS_LEVEL_NAMES = {0: "No access", 5: "Minimal", 10: "Guest", 15: "Planner", 20: "Reporter", 30: "Developer", 40: "Maintainer", 50: "Owner"}
# Levels highest-first, for stable access_details ordering.
LEVEL_ORDER = [ACCESS_LEVEL_NAMES[k] for k in sorted(ACCESS_LEVEL_NAMES, reverse=True)]

# GitLab group/project access-token bots, e.g. group_71834433_bot_<hash>.
_BOT_USERNAME = re.compile(r"^(group|project)_\d+_bot_", re.IGNORECASE)


def is_service_account(username):
    """True for missing usernames or GitLab bot-token accounts."""
    username = (username or "").strip()
    return not username or bool(_BOT_USERNAME.match(username))


class GitLab:
    def __init__(self, host, token, retries=5):
        self.base = f"{host.rstrip('/')}/api/v4"
        self.token = token
        self.retries = retries

    def _request(self, url):
        headers = {"PRIVATE-TOKEN": self.token, "Accept": "application/json"}
        for attempt in range(self.retries):
            try:
                resp = requests.get(url, headers=headers, timeout=60)
            except requests.RequestException:  # connection errors, read/connect timeouts, resets
                time.sleep(min(2 ** attempt, 30))
                continue
            if resp.status_code in (403, 404):  # restricted or missing: skip
                return None, {}
            if resp.status_code == 429 or resp.status_code >= 500:
                time.sleep(min(int(resp.headers.get("Retry-After", 2 ** attempt)), 30))
                continue
            resp.raise_for_status()
            return resp.json(), resp.headers
        print(f"warn: giving up after {self.retries} retries: {url.split('?')[0]}", file=sys.stderr)
        return None, {}

    def get(self, path):
        data, _ = self._request(f"{self.base}/{path}")
        return data

    def paged(self, path, params=None):
        query = urllib.parse.urlencode({**(params or {}), "per_page": 100})
        items, page = [], 1
        while True:
            data, headers = self._request(f"{self.base}/{path}?{query}&page={page}")
            if not data:
                break
            items.extend(data)
            nxt = headers.get("x-next-page")
            if not nxt:
                break
            page = int(nxt)
        return items


def scan(gl, root, include_projects, exclude_levels, enrich_email, workers):
    root_group = gl.get(f"groups/{urllib.parse.quote_plus(str(root))}")
    if not root_group:
        sys.exit(f"error: cannot read root group '{root}' (check token scope)")
    root_id = root_group["id"]

    groups = {root_id: root_group}
    for g in gl.paged(f"groups/{root_id}/descendant_groups"):
        groups[g["id"]] = g

    projects = {}
    if include_projects:
        for p in gl.paged(f"groups/{root_id}/projects", {"include_subgroups": "true"}):
            projects[p["id"]] = p

    print(f"scanning {len(groups)} groups, {len(projects)} projects ...", file=sys.stderr)

    # Scope catalog keyed by (kind, id) to avoid any group/project id overlap.
    scope_info = {}
    for gid, g in groups.items():
        scope_info[("group", gid)] = {"scope": g.get("full_path", str(gid)), "id": gid, "parent_id": g.get("parent_id")}
    for pid, p in projects.items():
        ns = p.get("namespace") or {}
        scope_info[("project", pid)] = {"scope": p.get("path_with_namespace", str(pid)), "id": pid, "parent_id": ns.get("id")}

    tasks = [("group", gid, f"groups/{gid}/members") for gid in groups]
    tasks += [("project", pid, f"projects/{pid}/members") for pid in projects]

    users = {}
    scope_access = defaultdict(lambda: defaultdict(set))  # (kind,id) -> {level_name: {uid}}
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(gl.paged, path): (stype, sid) for stype, sid, path in tasks}
        for fut in as_completed(futures):
            key = futures[fut]
            try:
                members = fut.result()
            except Exception as e:
                print(f"warn: skipped {key[0]} {key[1]}: {e}", file=sys.stderr)
                continue
            for m in members:
                uid = m["id"]
                if is_service_account(m.get("username")):
                    continue  # skip service/bot accounts
                level = m.get("access_level")
                if level in exclude_levels:
                    continue
                email = m.get("email") or m.get("public_email") or ""
                if uid not in users:
                    users[uid] = {"name": m.get("name", ""), "username": m.get("username", ""), "email": email}
                elif email and not users[uid]["email"]:
                    users[uid]["email"] = email
                scope_access[key][ACCESS_LEVEL_NAMES.get(level, str(level))].add(uid)

    if enrich_email:
        missing = [uid for uid, u in users.items() if not u["email"]]
        if missing:
            print(f"enriching email for {len(missing)} users ...", file=sys.stderr)
            with ThreadPoolExecutor(max_workers=workers) as ex:
                for uid, data in zip(missing, ex.map(lambda i: gl.get(f"users/{i}"), missing)):
                    if data:
                        users[uid]["email"] = data.get("email") or data.get("public_email") or ""

    scope_details, used = [], set()
    for key in sorted(scope_access, key=lambda k: scope_info[k]["scope"]):
        by_level = scope_access[key]
        access_details = {}
        for name in LEVEL_ORDER:
            if name in by_level:
                access_details[name] = sorted(by_level[name])
                used.update(by_level[name])
        info = scope_info[key]
        scope_details.append({"scope": info["scope"], "id": info["id"], "parent_id": info["parent_id"], "access_details": access_details})

    user_details = {str(uid): users[uid] for uid in sorted(used)}
    return [{"user_details": user_details, "scope_details": scope_details}]


def main():
    ap = argparse.ArgumentParser(description="Scan a GitLab group tree into a scope-centric access map (user.json shape).")
    ap.add_argument("-r", "--root", default=os.environ.get("GITLAB_ROOT", "konecorporation"), help="Root group id or full path (default: konecorporation).")
    ap.add_argument("-o", "--output", default="gitlab-access.json")
    ap.add_argument("--exclude-levels", default="", help="Comma-separated access levels to drop, e.g. 20 for the Reporter baseline (default: none).")
    ap.add_argument("--no-projects", action="store_true", help="Scan groups only, skip project (repo) members.")
    ap.add_argument("--no-email-enrich", action="store_true", help="Do not fetch /users/:id to fill missing emails.")
    ap.add_argument("-w", "--workers", type=int, default=8)
    args = ap.parse_args()

    token = os.environ.get("TF_VAR_gitlab_token") or os.environ.get("GITLAB_TOKEN")
    if not token:
        sys.exit("error: set TF_VAR_gitlab_token (or GITLAB_TOKEN) to an admin/owner token with api scope")

    exclude = {int(x) for x in args.exclude_levels.split(",") if x.strip()}
    gl = GitLab(os.environ.get("GITLAB_HOST", "https://gitlab.com"), token)
    result = scan(gl, args.root, not args.no_projects, exclude, not args.no_email_enrich, args.workers)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    doc = result[0]
    print(f"wrote {args.output}: {len(doc['user_details'])} users, {len(doc['scope_details'])} scopes", file=sys.stderr)


if __name__ == "__main__":
    main()
