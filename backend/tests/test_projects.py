"""Tests for project endpoints: create project, create milestone, update milestone."""

import pytest


# ── Create Project ───────────────────────────────────────────────────

async def test_create_project(auth_client):
    resp = await auth_client.post("/projects", json={
        "name": "Portfolio Website",
        "description": "Personal portfolio with React",
        "priority": 1,
        "tech_stack": "React, Tailwind",
        "milestones": [
            {"title": "Design mockup", "order_index": 0},
            {"title": "Build frontend", "order_index": 1},
        ],
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Portfolio Website"
    assert data["priority"] == 1
    assert data["status"] == "not_started"
    assert len(data["milestones"]) == 2


# ── Create Milestone ─────────────────────────────────────────────────

async def test_create_milestone(auth_client):
    # Create a project first
    proj = await auth_client.post("/projects", json={
        "name": "API Project",
        "priority": 2,
    })
    project_id = proj.json()["id"]

    resp = await auth_client.post(f"/projects/{project_id}/milestones", json={
        "title": "Write API docs",
        "order_index": 0,
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Write API docs"
    assert data["status"] == "pending"
    assert data["project_id"] == project_id


# ── Update Milestone Status ──────────────────────────────────────────

async def test_update_milestone_status(auth_client):
    # Create project with milestone
    proj = await auth_client.post("/projects", json={
        "name": "ML Project",
        "priority": 1,
        "milestones": [{"title": "Train model", "order_index": 0}],
    })
    milestone_id = proj.json()["milestones"][0]["id"]

    resp = await auth_client.put(f"/projects/milestones/{milestone_id}", json={
        "status": "in_progress",
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "in_progress"

    # Complete it
    resp2 = await auth_client.put(f"/projects/milestones/{milestone_id}", json={
        "status": "complete",
    })
    assert resp2.status_code == 200
    assert resp2.json()["status"] == "complete"
    assert resp2.json()["completed_at"] is not None
