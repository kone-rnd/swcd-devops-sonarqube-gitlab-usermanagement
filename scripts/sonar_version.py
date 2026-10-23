#!/usr/bin/env python3
"""Terraform external data source: print {"version": "<sonarqube version>"}.

Reads {"host": "..."} on stdin and the token from SONARQUBE_TOKEN (or SONAR_TOKEN).
Uses the unrestricted GET /api/server/version, so the provider
never needs the privileged /api/system/info probe and no version is passed by hand.

Uses the requests library (not urllib) so only http/https are ever requested.
"""
import base64
import json
import os
import sys

import requests

query = json.load(sys.stdin)
host = query["host"].rstrip("/")
token = os.environ.get("SONARQUBE_TOKEN") or os.environ.get("SONAR_TOKEN")

resp = requests.get(
    f"{host}/api/server/version",
    headers={"Authorization": "Basic " + base64.b64encode(f"{token}:".encode()).decode()},
    timeout=30,
)
resp.raise_for_status()

json.dump({"version": resp.text.strip()}, sys.stdout)
