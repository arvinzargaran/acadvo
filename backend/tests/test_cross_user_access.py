"""Cross-tenant access regression tests.

Every endpoint that takes a resource ID is exercised twice: once as the owner
(to prove the fixture is real and the route works) and once as a *different*
signed-in user, who must get a 404 rather than the record.

These are pure regression guards. The ownership checks they cover are correct
today — the risk is a future refactor that changes a `.where(id == x, user_id ==
me)` into a plain primary-key lookup. Nothing in the product breaks when that
happens; only a test like this notices.

404 rather than 403 is deliberate throughout: a 403 confirms the ID exists,
which leaks the shape of other users' data.
"""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.services.auth import create_access_token, hash_password
from tests.conftest import CSRF_HEADERS


@pytest.fixture
async def other_user(db):
    """A second, unrelated account — the 'attacker' in each test below."""
    from app.models.user import User

    user = User(
        id=uuid.uuid4(),
        email="intruder@example.com",
        hashed_password=hash_password("testpass123"),
        full_name="Intruder",
        university="University of Toronto",
        program="Computer Science",
        email_verified=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest.fixture
async def other_client(app, other_user):
    """Authenticated client for the second account."""
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        cookies={"access_token": create_access_token(other_user.id)},
        headers=CSRF_HEADERS,
    ) as c:
        yield c


# ── Projects and milestones ──────────────────────────────────────────

async def test_cannot_touch_another_users_project(auth_client, other_client):
    created = await auth_client.post("/projects", json={"name": "Mine", "priority": 1})
    assert created.status_code == 201
    project_id = created.json()["id"]

    # Owner can read it.
    assert (await auth_client.get(f"/projects/{project_id}")).status_code == 200

    # The other user cannot read, edit, or delete it.
    assert (await other_client.get(f"/projects/{project_id}")).status_code == 404
    assert (await other_client.put(f"/projects/{project_id}", json={"name": "Stolen"})).status_code == 404
    assert (await other_client.delete(f"/projects/{project_id}")).status_code == 404

    # And it is untouched.
    assert (await auth_client.get(f"/projects/{project_id}")).json()["name"] == "Mine"


async def test_cannot_add_a_milestone_to_another_users_project(auth_client, other_client):
    """The nested-resource case: the PARENT's owner is what matters."""
    created = await auth_client.post("/projects", json={"name": "Mine", "priority": 1})
    project_id = created.json()["id"]

    resp = await other_client.post(
        f"/projects/{project_id}/milestones", json={"title": "Injected", "order_index": 0}
    )
    assert resp.status_code == 404

    milestones = (await auth_client.get(f"/projects/{project_id}")).json().get("milestones", [])
    assert milestones == []


async def test_cannot_touch_another_users_milestone(auth_client, other_client):
    created = await auth_client.post("/projects", json={"name": "Mine", "priority": 1})
    project_id = created.json()["id"]
    milestone = await auth_client.post(
        f"/projects/{project_id}/milestones", json={"title": "Ship it", "order_index": 0}
    )
    assert milestone.status_code == 201
    milestone_id = milestone.json()["id"]

    # Reached by child id alone — ownership must resolve through the parent.
    assert (await other_client.put(f"/projects/milestones/{milestone_id}", json={"title": "Hijacked"})).status_code == 404
    assert (await other_client.delete(f"/projects/milestones/{milestone_id}")).status_code == 404

    assert (await auth_client.put(
        f"/projects/milestones/{milestone_id}", json={"title": "Ship it v2"}
    )).status_code == 200


async def test_project_list_is_scoped_to_the_caller(auth_client, other_client):
    await auth_client.post("/projects", json={"name": "Mine", "priority": 1})
    await other_client.post("/projects", json={"name": "Theirs", "priority": 1})

    mine = [p["name"] for p in (await auth_client.get("/projects")).json()]
    theirs = [p["name"] for p in (await other_client.get("/projects")).json()]
    assert mine == ["Mine"]
    assert theirs == ["Theirs"]


# ── Career targets and timeline ──────────────────────────────────────

async def test_cannot_touch_another_users_career_target(auth_client, other_client):
    created = await auth_client.post(
        "/career/targets", json={"company_name": "Shopify", "status": "researching"}
    )
    assert created.status_code == 201
    target_id = created.json()["id"]

    assert (await other_client.put(
        f"/career/targets/{target_id}", json={"company_name": "Hijacked"}
    )).status_code == 404
    assert (await other_client.delete(f"/career/targets/{target_id}")).status_code == 404

    still_mine = (await auth_client.get("/career/targets")).json()
    assert still_mine[0]["company_name"] == "Shopify"


async def test_cannot_delete_another_users_timeline_event(auth_client, other_client):
    created = await auth_client.post("/career/timeline", json={
        "title": "Interview", "event_date": "2026-10-01", "category": "deadline",
    })
    assert created.status_code == 201
    event_id = created.json()["id"]

    assert (await other_client.delete(f"/career/timeline/{event_id}")).status_code == 404
    assert len((await auth_client.get("/career/timeline")).json()) == 1


async def test_career_lists_are_scoped_to_the_caller(auth_client, other_client):
    await auth_client.post("/career/targets", json={"company_name": "Mine", "status": "researching"})
    assert (await other_client.get("/career/targets")).json() == []


# ── Conversations ────────────────────────────────────────────────────

async def test_cannot_read_or_delete_another_users_conversation(auth_client, other_client):
    created = await auth_client.post("/conversations", json={"title": "Private chat"})
    assert created.status_code == 200
    conversation_id = created.json()["id"]

    assert (await other_client.get(f"/conversations/{conversation_id}")).status_code == 404
    assert (await other_client.delete(f"/conversations/{conversation_id}")).status_code == 404

    assert (await auth_client.get(f"/conversations/{conversation_id}")).status_code == 200


async def test_cannot_post_a_message_into_another_users_conversation(auth_client, other_client):
    """The AI reads the conversation's owner context — posting into someone
    else's thread would leak their data into a reply the intruder receives."""
    created = await auth_client.post("/conversations", json={"title": "Private chat"})
    conversation_id = created.json()["id"]

    resp = await other_client.post(
        f"/conversations/{conversation_id}/messages", json={"content": "who am I?"}
    )
    assert resp.status_code == 404


async def test_conversation_list_is_scoped_to_the_caller(auth_client, other_client):
    await auth_client.post("/conversations", json={"title": "Mine"})
    assert (await other_client.get("/conversations")).json() == []


# ── DSA problems and settings ────────────────────────────────────────

async def test_cannot_touch_another_users_dsa_problem(auth_client, other_client):
    created = await auth_client.post("/dsa/problems", json={
        "title": "Two Sum", "difficulty": "easy", "pattern": "arrays",
    })
    assert created.status_code == 201
    problem_id = created.json()["id"]

    assert (await other_client.put(
        f"/dsa/problems/{problem_id}", json={"title": "Hijacked"}
    )).status_code == 404
    assert (await other_client.delete(f"/dsa/problems/{problem_id}")).status_code == 404

    assert (await auth_client.get("/dsa/problems")).json()[0]["title"] == "Two Sum"


async def test_dsa_data_is_scoped_to_the_caller(auth_client, other_client):
    await auth_client.post("/dsa/problems", json={
        "title": "Two Sum", "difficulty": "easy", "pattern": "arrays",
    })
    assert (await other_client.get("/dsa/problems")).json() == []
    assert (await other_client.get("/dsa/stats")).json()["total_solved"] == 0


async def test_dsa_settings_are_per_user(auth_client, other_client):
    await auth_client.put("/dsa/settings", json={"weekly_goal": 12})
    assert (await auth_client.get("/dsa/settings")).json()["weekly_goal"] == 12
    # The other account keeps its own default, unaffected.
    assert (await other_client.get("/dsa/settings")).json()["weekly_goal"] != 12


# ── Suggestions ──────────────────────────────────────────────────────

async def test_cannot_update_another_users_suggestion(auth_client, other_client, db, test_user):
    from app.models.suggestion import AISuggestion, SuggestionType

    suggestion = AISuggestion(
        id=uuid.uuid4(),
        user_id=test_user.id,
        suggestion_type=SuggestionType.course,
        content="Take EECS 3101 next term",
    )
    db.add(suggestion)
    await db.commit()

    resp = await other_client.put(
        f"/suggestions/{suggestion.id}", json={"accepted": True}
    )
    assert resp.status_code == 404

    assert (await other_client.get("/suggestions")).json() == []
    assert len((await auth_client.get("/suggestions")).json()) == 1


# ── Course recommendations ───────────────────────────────────────────

async def test_cannot_accept_another_users_recommendation(auth_client, other_client, db, test_user):
    from app.models.course_recommendation import CourseRecommendation

    rec = CourseRecommendation(
        id=uuid.uuid4(),
        user_id=test_user.id,
        semester="Fall 2026",
        course_code="LE/EECS 3101",
        course_name="Algorithms",
        reasoning="Required for the major",
    )
    db.add(rec)
    await db.commit()

    assert (await other_client.post(f"/course-advisor/recommendations/{rec.id}/accept")).status_code == 404
    assert (await other_client.post(f"/course-advisor/recommendations/{rec.id}/dismiss")).status_code == 404
    assert (await other_client.get("/course-advisor/recommendations")).json() == []


# ── Degree data (already covered for assessments/buckets; these fill gaps) ──

async def test_cannot_touch_another_users_course(auth_client, other_client):
    created = await auth_client.post("/degree/courses", json={
        "course_code": "CSC148", "course_name": "Intro", "credit_value": 3.0,
    })
    assert created.status_code == 201
    course_id = created.json()["id"]

    assert (await other_client.put(f"/degree/courses/{course_id}", json={"grade": "F"})).status_code == 404
    assert (await other_client.delete(f"/degree/courses/{course_id}")).status_code == 404
    assert (await other_client.get("/degree/courses")).json() == []

    assert (await auth_client.get("/degree/courses")).json()[0]["course_code"] == "CSC148"


async def test_cannot_update_another_users_requirement(auth_client, other_client):
    created = await auth_client.post(
        "/degree/requirements", json={"bucket_name": "Major", "credits_required": 60}
    )
    assert created.status_code == 201
    requirement_id = created.json()["id"]

    resp = await other_client.put(
        f"/degree/requirements/{requirement_id}", json={"credits_required": 6}
    )
    assert resp.status_code == 404


# ── Study sessions ───────────────────────────────────────────────────

async def test_study_stats_are_scoped_to_the_caller(auth_client, other_client):
    logged = await auth_client.post("/study/session", json={"duration_minutes": 45})
    assert logged.status_code == 200

    mine = (await auth_client.get("/study/stats")).json()
    theirs = (await other_client.get("/study/stats")).json()
    assert mine["today_minutes"] >= 45
    assert theirs["today_minutes"] == 0
    assert theirs["current_streak"] == 0


# ── A nonexistent id must look identical to someone else's id ────────

@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/projects/{id}"),
        ("PUT", "/projects/{id}"),
        ("DELETE", "/projects/{id}"),
        ("PUT", "/degree/courses/{id}"),
        ("DELETE", "/degree/courses/{id}"),
        ("PUT", "/career/targets/{id}"),
        ("DELETE", "/career/targets/{id}"),
        ("GET", "/conversations/{id}"),
        ("DELETE", "/conversations/{id}"),
        ("PUT", "/dsa/problems/{id}"),
        ("DELETE", "/dsa/problems/{id}"),
    ],
)
async def test_unknown_id_is_404_not_403(auth_client, method, path):
    """A 403 would confirm the id exists and belongs to someone — an
    enumeration oracle. Every one of these must be indistinguishable from
    'no such record'."""
    resp = await auth_client.request(method, path.format(id=uuid.uuid4()), json={})
    assert resp.status_code == 404
