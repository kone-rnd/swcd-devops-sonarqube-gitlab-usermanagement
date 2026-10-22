#!/usr/bin/env python3
"""Terraform external data source: print {"version": "<sonarqube version>"}.

Reads {"host": "..."} on stdin and the token from TF_VAR_sonarqube_token
(or SONAR_TOKEN). Uses the unrestricted GET /api/server/version, so the provider
never needs the privileged /api/system/info probe and no version is passed by hand.
"""
import base64
import json
import os
import sys
import urllib.request

query = json.load(sys.stdin)
host = query["host"].rstrip("/")
token = os.environ.get("TF_VAR_sonarqube_token")

req = urllib.request.Request(
    f"{host}/api/server/version",
    headers={"Authorization": "Basic " + base64.b64encode(f"{token}:".encode()).decode()},
)
with urllib.request.urlopen(req, timeout=30) as r:
    version = r.read().decode().strip()

json.dump({"version": version}, sys.stdout)
