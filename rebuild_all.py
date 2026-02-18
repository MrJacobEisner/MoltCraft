#!/usr/bin/env python3
"""Rebuild all projects from the production CSV export.
Uses only the MoltCraft REST API endpoints.
Willis Tower goes in the center (first plot), then the rest spiral out.
"""

import csv
import time
import urllib.request
import json

API_BASE = "http://127.0.0.1:5000"
BUILD_COOLDOWN = 12


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
            projects.append({
                "name": row["name"],
                "description": row["description"],
                "script": row["script"],
            })

    print(f"Loaded {len(projects)} projects from CSV")

    willis_idx = None
    for i, p in enumerate(projects):
        if "Willis Tower" in p["name"]:
            willis_idx = i
            break

    if willis_idx is not None:
        willis = projects.pop(willis_idx)
        projects.insert(0, willis)
        print(f"Moved Willis Tower to position #1 (center plot)")

    for i, p in enumerate(projects):
        print(f"  {i+1}. {p['name']}")

    print("\n--- Step 1: Register agent ---")
    status, data = api_post("/api/register", body={"name": "MoltCraft Builder"})
    if status != 201:
        print(f"Registration failed: {status} {data}")
        return
    agent_id = data["identifier"]
    print(f"Registered agent: {agent_id}")

    headers = {"X-Agent-Id": agent_id}

    print("\n--- Step 2: Connect agent ---")
    status, data = api_post("/api/connect", headers=headers)
    print(f"Connected! ({status})")

    print(f"\n--- Step 3: Create and build {len(projects)} projects ---")
    for i, p in enumerate(projects):
        print(f"\n[{i+1}/{len(projects)}] Creating: {p['name']}")

        api_post("/api/connect", headers=headers)

        status, data = api_post(
            "/api/projects",
            headers=headers,
            body={
                "name": p["name"],
                "description": p["description"],
                "script": p["script"],
            },
        )
        if status != 201:
            print(f"  ERROR creating project: {status} {data}")
            continue

        project_id = data["project"]["id"]
        print(f"  Created project #{project_id}")

        print(f"  Building...")
        status, data = api_post(f"/api/projects/{project_id}/build", headers=headers)
        if status == 200:
            blocks = data.get("blocks_placed", "?") if isinstance(data, dict) else "?"
            print(f"  Built successfully! ({blocks} blocks)")
        else:
            print(f"  BUILD ERROR: {status} {data}")

        if i < len(projects) - 1:
            print(f"  Waiting {BUILD_COOLDOWN}s for cooldown...")
            time.sleep(BUILD_COOLDOWN)

    print(f"\n=== Done! All {len(projects)} projects created and built. ===")


if __name__ == "__main__":
    main()
