#!/usr/bin/env python3
"""Continue rebuild from project 7 onward (projects 1-6 already built)."""

import csv
import time
import urllib.request
import json
import sys

API_BASE = "http://127.0.0.1:5000"
AGENT_ID = "mc_04f21c13"
START_FROM = int(sys.argv[1]) if len(sys.argv) > 1 else 5

def api_post(path, headers=None, body=None):
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(
        f"{API_BASE}{path}",
        data=data,
        headers={**(headers or {}), "Content-Type": "application/json"} if data else (headers or {}),
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:300]

def main():
    projects = []
    with open("attached_assets/projects_1771399460578.csv", "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            projects.append({"name": row["name"], "description": row["description"], "script": row["script"]})

    willis_idx = None
    for i, p in enumerate(projects):
        if "Willis Tower" in p["name"]:
            willis_idx = i
            break
    if willis_idx is not None:
        willis = projects.pop(willis_idx)
        projects.insert(0, willis)

    remaining = projects[START_FROM - 1:]
    print(f"Continuing from project {START_FROM}, {len(remaining)} projects to build")

    headers = {"X-Agent-Id": AGENT_ID}
    api_post("/api/connect", headers=headers)

    for i, p in enumerate(remaining):
        idx = START_FROM + i
        print(f"\n[{idx}/18] Creating: {p['name']}")
        api_post("/api/connect", headers=headers)
        status, data = api_post("/api/projects", headers=headers,
            body={"name": p["name"], "description": p["description"], "script": p["script"]})
        if status != 201:
            print(f"  ERROR: {status} {data}")
            continue
        project_id = data["project"]["id"]
        print(f"  Created #{project_id}, building...")
        status, data = api_post(f"/api/projects/{project_id}/build", headers=headers)
        if status == 200:
            print(f"  SUCCESS")
        else:
            print(f"  BUILD ERROR: {status} {data}")
        if i < len(remaining) - 1:
            time.sleep(2)

    print(f"\n=== Done! ===")

if __name__ == "__main__":
    main()
