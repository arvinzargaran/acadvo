"""`GET /users/me/export` — the access side of PIPEDA Principle 9.

The interesting test here is `test_every_user_owned_table_is_in_the_export`. The
export is only a real answer to "give me my data" if it stays complete as the
schema grows, and the way that quietly stops being true is a new feature adding
a table nobody thinks to add here. That test derives the expected set from the
foreign keys, so a new user-owned table is covered the moment it exists — or the
suite fails and says so.

The second thing under test is scoping. An export assembled with a missing
`where` clause still returns a plausible-looking document; it just contains
someone else's grades.
"""
import uuid

import pytest

from app.database import Base
from app.services.data_export import (
    REDACTED_COLUMNS,
    REDACTED_PLACEHOLDER,
    _user_owned_tables,
    export_user_data,
)


@pytest.fixture
async def user_with_data(db, test_user):
    """Give the account rows at each depth of the ownership graph."""
    from app.models.conversation import Conversation
    from app.models.degree import Course, DegreeRequirement, Assessment
    from app.models.message import Message, MessageRole
    from app.models.project import Project

    bucket = DegreeRequirement(
        id=uuid.uuid4(),
        user_id=test_user.id,
        bucket_name="Major Credits",
        credits_required=42.0,
    )
    db.add(bucket)
    await db.flush()

    course = Course(
        id=uuid.uuid4(),
        user_id=test_user.id,
        course_code="EECS 2011",
        course_name="Fundamentals of Data Structures",
        credit_value=3.0,
        grade="A",
    )
    db.add(course)
    await db.flush()

    db.add(
        Assessment(
            id=uuid.uuid4(),
            course_id=course.id,
            title="Midterm",
            weight=30.0,
        )
    )

    conversation = Conversation(id=uuid.uuid4(), user_id=test_user.id, title="Planning")
    db.add(conversation)
    await db.flush()
    db.add(
        Message(
            id=uuid.uuid4(),
            conversation_id=conversation.id,
            role=MessageRole.user,
            content="Which electives fit next term?",
        )
    )

    db.add(Project(id=uuid.uuid4(), user_id=test_user.id, name="Portfolio site", priority=1))
    await db.commit()
    return test_user


async def test_every_user_owned_table_is_in_the_export(user_with_data, db):
    """A table that belongs to a user must appear, or the export under-reports.

    Derived from the schema rather than listed, so this keeps holding for tables
    that do not exist yet.
    """
    payload = await export_user_data(db, user_with_data.id)

    expected = set(_user_owned_tables())
    assert expected, "the ownership walk found nothing — it is broken, not the schema"
    assert set(payload["tables"]) == expected

    # And the walk itself must agree with the delete cascade: everything with a
    # foreign key into users (directly or transitively) and nothing global.
    assert "catalog_courses" not in expected, "shared reference data is not personal information"
    assert {"conversations", "courses", "projects", "dsa_settings"} <= expected
    assert {"assessments", "messages", "milestones"} <= expected, "indirect children must be reached"


async def test_export_contains_the_users_own_rows(user_with_data, db):
    payload = await export_user_data(db, user_with_data.id)

    assert payload["account"]["email"] == "test@example.com"
    codes = [row["course_code"] for row in payload["tables"]["courses"]]
    assert "EECS 2011" == codes[0]
    assert [row["title"] for row in payload["tables"]["assessments"]] == ["Midterm"]
    assert payload["tables"]["messages"][0]["content"] == "Which electives fit next term?"


async def test_export_excludes_other_accounts(user_with_data, db):
    """A second account's rows must not appear in the first account's export."""
    from app.models.degree import Course
    from app.models.user import User
    from app.services.auth import hash_password

    stranger = User(
        id=uuid.uuid4(),
        email="stranger@example.com",
        hashed_password=hash_password("testpass123"),
        full_name="Stranger",
        email_verified=True,
    )
    db.add(stranger)
    await db.flush()
    db.add(
        Course(
            id=uuid.uuid4(),
            user_id=stranger.id,
            course_code="MATH 1013",
            course_name="Applied Calculus",
            credit_value=3.0,
        )
    )
    await db.commit()

    payload = await export_user_data(db, user_with_data.id)

    serialised = str(payload)
    assert "stranger@example.com" not in serialised
    assert "MATH 1013" not in serialised


async def test_credentials_are_redacted_not_exported(user_with_data, db):
    """The export must not hand back material that can be replayed as the user."""
    payload = await export_user_data(db, user_with_data.id)

    assert payload["account"]["hashed_password"] == REDACTED_PLACEHOLDER
    assert payload["account"]["calendar_token"] == REDACTED_PLACEHOLDER
    # The key still exists: the export says what is held, then declines to send it.
    assert "hashed_password" in payload["account"]


async def test_session_tokens_in_child_tables_are_redacted_too(user_with_data, db):
    """`refresh_tokens.token` is a live credential, not personal information.

    The account row is the obvious place to look for secrets and the easy one to
    remember; the child tables are where a leak would actually be shipped. A
    refresh token in a downloadable file is a session anyone holding that file
    can resume.
    """
    from datetime import datetime, timedelta, timezone

    from app.models.user import RefreshToken, VerificationToken

    db.add(
        RefreshToken(
            id=uuid.uuid4(),
            user_id=user_with_data.id,
            token="a-real-looking-refresh-token",
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
    )
    db.add(
        VerificationToken(
            id=uuid.uuid4(),
            user_id=user_with_data.id,
            token_hash="0" * 64,
            purpose="email_verify",
            expires_at=datetime.now(timezone.utc) + timedelta(days=1),
        )
    )
    await db.commit()

    payload = await export_user_data(db, user_with_data.id)

    assert payload["tables"]["refresh_tokens"][0]["token"] == REDACTED_PLACEHOLDER
    assert payload["tables"]["verification_tokens"][0]["token_hash"] == REDACTED_PLACEHOLDER
    assert "a-real-looking-refresh-token" not in str(payload)


async def test_values_survive_json_encoding(user_with_data, db):
    """Whatever comes back must actually serialise — no UUID/Decimal landmines."""
    import json

    payload = await export_user_data(db, user_with_data.id)
    json.dumps(payload)  # raises on any non-encodable value


async def test_endpoint_requires_authentication(client):
    response = await client.get("/users/me/export")
    assert response.status_code == 401


async def test_endpoint_returns_an_attachment(auth_client):
    response = await auth_client.get("/users/me/export")

    assert response.status_code == 200
    disposition = response.headers["content-disposition"]
    assert disposition.startswith("attachment;")
    assert "acadvo-export-" in disposition
    # A page of someone's grades must not be cached anywhere on the way back.
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["export_format"] == "acadvo-account-export/1"


async def test_tables_in_the_export_match_the_models_registry(db, test_user):
    """Guard the walk itself: no table in the schema is silently unclassified."""
    payload = await export_user_data(db, test_user.id)

    known = set(Base.metadata.tables) - {"users"}
    classified = set(payload["tables"]) | {
        # Shared reference data — the same rows for every student, so not
        # personal information and deliberately out of scope.
        "catalog_courses",
        "requirement_rules",
        "program_research_jobs",
    }
    assert known <= classified, f"unclassified tables: {known - classified}"


# ---------------------------------------------------------------------------
# The graph walk, against shapes this schema does not have yet
# ---------------------------------------------------------------------------
#
# The value of deriving the export from foreign keys is that the *next* schema
# change is handled without touching data_export.py. These tests build a
# throwaway schema containing the shapes that would break a naive walk — a
# foreign key aimed at a unique column instead of the primary key, a nullable
# owner link alongside a mandatory one, a self-reference, a composite primary
# key, two paths back to the account — and run the real exporter over it.


@pytest.fixture
def synthetic_schema():
    """A miniature ownership graph with every awkward foreign-key shape in it."""
    from sqlalchemy import Column, ForeignKey, MetaData, String, Table

    meta = MetaData()
    Table(
        "accounts",
        meta,
        Column("id", String(36), primary_key=True),
        # Referenced by `notes` below: a foreign key is allowed to point at any
        # unique column, not just the primary key.
        Column("handle", String(64), unique=True, nullable=False),
    )
    Table(
        "folders",
        meta,
        Column("id", String(36), primary_key=True),
        Column("account_id", String(36), ForeignKey("accounts.id"), nullable=False),
    )
    Table(
        "notes",
        meta,
        Column("id", String(36), primary_key=True),
        Column("account_handle", String(64), ForeignKey("accounts.handle"), nullable=False),
        Column("body", String(255)),
    )
    Table(
        "items",
        meta,
        Column("id", String(36), primary_key=True),
        # Mandatory link to the folder, optional direct link to the account: two
        # paths home, and the optional one is the trap.
        Column("folder_id", String(36), ForeignKey("folders.id"), nullable=False),
        Column("account_id", String(36), ForeignKey("accounts.id"), nullable=True),
        Column("parent_item_id", String(36), ForeignKey("items.id"), nullable=True),
        Column("label", String(255)),
    )
    Table(
        "tags",
        meta,
        Column("account_id", String(36), ForeignKey("accounts.id"), primary_key=True),
        Column("name", String(64), primary_key=True),
    )
    return meta


@pytest.fixture
async def synthetic_data(db, synthetic_schema):
    """Two accounts' worth of rows in the synthetic schema."""
    meta = synthetic_schema

    def _create(sync_session):
        meta.create_all(sync_session.connection())

    await db.run_sync(_create)

    mine, theirs = str(uuid.uuid4()), str(uuid.uuid4())
    await db.execute(
        meta.tables["accounts"].insert(),
        [
            {"id": mine, "handle": "mine"},
            {"id": theirs, "handle": "theirs"},
        ],
    )
    await db.execute(
        meta.tables["folders"].insert(),
        [
            {"id": "folder-mine", "account_id": mine},
            {"id": "folder-theirs", "account_id": theirs},
        ],
    )
    await db.execute(
        meta.tables["notes"].insert(),
        [
            {"id": "note-mine", "account_handle": "mine", "body": "my note"},
            {"id": "note-theirs", "account_handle": "theirs", "body": "their note"},
        ],
    )
    await db.execute(
        meta.tables["items"].insert(),
        [
            {"id": "item-linked", "folder_id": "folder-mine", "account_id": mine, "label": "linked"},
            # The row the naive walk loses: it belongs to my folder, but its
            # optional direct account link was never set.
            {"id": "item-orphan", "folder_id": "folder-mine", "account_id": None, "label": "orphan"},
            {"id": "item-theirs", "folder_id": "folder-theirs", "account_id": theirs, "label": "theirs"},
        ],
    )
    await db.execute(
        meta.tables["tags"].insert(),
        [
            {"account_id": mine, "name": "urgent"},
            {"account_id": theirs, "name": "secret"},
        ],
    )
    await db.commit()
    yield meta, mine, theirs

    def _drop(sync_session):
        meta.drop_all(sync_session.connection())

    await db.run_sync(_drop)
    await db.commit()


async def test_scoping_prefers_a_mandatory_link_over_an_optional_one(synthetic_schema):
    """Scoping on a nullable foreign key drops every row where it is NULL.

    Delete this and `_scoping_candidates` is free to pick the optional direct
    link, which quietly under-reports exactly the rows nobody filed properly.
    """
    from app.services.data_export import _scoping_candidates

    items = synthetic_schema.tables["items"]
    best = _scoping_candidates(items, {"accounts", "folders", "items"}, root="accounts")[0]
    assert best.parent.name == "folder_id"

    # And the table's own primary key is never a scoping option: its ids do not
    # exist until after it has been read.
    assert "parent_item_id" not in {fk.parent.name for fk in _scoping_candidates(
        items, {"accounts", "folders", "items"}, root="accounts"
    )}


async def test_export_reaches_rows_whose_optional_owner_link_is_null(db, synthetic_data):
    """A row owned only through its parent must still be exported.

    Without this, `items` gets scoped on its nullable `account_id` and every
    row that never had one is missing from the person's copy of their data.
    """
    from app.services.data_export import export_user_data

    meta, mine, _ = synthetic_data
    payload = await export_user_data(db, mine, metadata=meta, root="accounts")

    labels = sorted(row["label"] for row in payload["tables"]["items"])
    assert labels == ["linked", "orphan"]


async def test_export_follows_a_key_that_points_at_a_non_primary_key_column(db, synthetic_data):
    """`notes.account_handle` references `accounts.handle`, not `accounts.id`.

    Collecting "the parent's first primary key column" and comparing it against
    a handle column matches nothing, so the whole table silently exports empty.
    """
    from app.services.data_export import export_user_data

    meta, mine, _ = synthetic_data
    payload = await export_user_data(db, mine, metadata=meta, root="accounts")

    assert [row["body"] for row in payload["tables"]["notes"]] == ["my note"]


async def test_export_of_a_synthetic_schema_never_crosses_accounts(db, synthetic_data):
    """The highest-severity failure: another account's rows in this export.

    Every awkward shape in the synthetic schema is a chance to lose the scoping
    predicate. Nothing belonging to the other account may appear anywhere.
    """
    from app.services.data_export import export_user_data

    meta, mine, theirs = synthetic_data
    payload = await export_user_data(db, mine, metadata=meta, root="accounts")

    serialised = str(payload)
    for stranger_value in (theirs, "theirs", "their note", "folder-theirs", "secret"):
        assert stranger_value not in serialised, f"leaked {stranger_value!r}"

    # A composite-primary-key table still gets exported (and scoped).
    assert [row["name"] for row in payload["tables"]["tags"]] == ["urgent"]
    # Every table in the synthetic graph was reached, none stranded by the
    # self-reference or by waiting on a parent forever.
    assert set(payload["tables"]) == {"folders", "notes", "items", "tags"}


# ---------------------------------------------------------------------------
# Cost, redaction and response shape
# ---------------------------------------------------------------------------


async def test_export_caps_rows_per_table_and_says_that_it_did(db, test_user, monkeypatch):
    """One request must not read an unbounded number of rows into memory.

    Row counts here are user-driven, so without a cap an old or abusive account
    turns this endpoint into a memory and connection sink — and the `IN (...)`
    lists it builds for child tables would blow past Postgres' bind-parameter
    ceiling. The truncation has to be announced, or the export lies about being
    complete.
    """
    from datetime import date

    from app.models.study import StudySession
    from app.services import data_export

    for day in range(1, 4):
        db.add(
            StudySession(
                id=uuid.uuid4(),
                user_id=test_user.id,
                duration_minutes=30,
                date=date(2026, 1, day),
            )
        )
    await db.commit()

    monkeypatch.setattr(data_export, "MAX_ROWS_PER_TABLE", 2)
    payload = await data_export.export_user_data(db, test_user.id)

    assert len(payload["tables"]["study_sessions"]) == 2
    assert "study_sessions" in payload["truncated_tables"]
    assert payload["max_rows_per_table"] == 2


async def test_enum_columns_export_as_plain_strings(user_with_data, db):
    """`CourseStatus` is a `str, enum.Enum`, so a `str` check matches the member.

    Left unhandled, the payload carries enum objects that only survive because
    `json.dumps` happens to render their string value; anything else that reads
    the document — another serialiser, a comparison, a diff — sees
    `CourseStatus.not_scheduled`.
    """
    payload = await export_user_data(db, user_with_data.id)

    status = payload["tables"]["courses"][0]["status"]
    assert type(status) is str
    assert status == "not_scheduled"


async def test_no_credential_column_escapes_the_redaction_list():
    """A new secret column must be redacted, not exported because nobody noticed.

    `REDACTED_COLUMNS` is a hand-written list, which is the same failure mode
    the table walk exists to avoid. This derives the suspects from the schema:
    add `api_key` or `session_token` to any model and the suite says so.
    """
    from app.services.data_export import REDACTED_COLUMNS

    suspicious = ("password", "secret", "token", "api_key", "apikey", "private_key")
    missed = {
        f"{table.name}.{column.name}"
        for table in Base.metadata.tables.values()
        for column in table.columns
        if any(word in column.name.lower() for word in suspicious)
        and column.name not in REDACTED_COLUMNS
    }
    assert not missed, f"credential-looking columns not redacted: {sorted(missed)}"


async def test_export_endpoint_is_actually_rate_limited(auth_client):
    """`5/hour` is a decorator; slowapi silently no-ops without `request: Request`.

    The export is the most expensive authenticated GET in the API, so the limit
    is the only thing standing between one account and repeated full-database
    reads. Nothing else in the suite runs with the limiter enabled, so if this
    test goes away a refactor that drops the `request` parameter looks fine.
    """
    from app.limiter import limiter

    limiter._storage.reset()
    limiter.enabled = True
    try:
        statuses = [(await auth_client.get("/users/me/export")).status_code for _ in range(6)]
    finally:
        limiter.enabled = False
        limiter._storage.reset()

    assert statuses[:5] == [200] * 5
    assert statuses[5] == 429


def test_the_model_marker_redacts_a_column_its_name_would_not():
    """A credential is protected by the marker, not by being named like one.

    The name list only catches columns someone already thought about. This
    module's premise is that a new table joins the export without anyone reading
    it — so the marker has to be what carries the safety property, or a future
    `otp_secret` ships in a downloadable file.
    """
    from sqlalchemy import Column, MetaData, String, Table as SATable

    from app.services.data_export import _is_redacted

    metadata = MetaData()
    table = SATable(
        "gadgets",
        metadata,
        Column("harmless", String),
        Column("recovery_code", String, info={"export": "redact"}),
    )

    assert _is_redacted(table.c.recovery_code)
    assert not _is_redacted(table.c.harmless)


def test_every_credential_column_carries_the_marker():
    """The marker must be on the real columns, not just supported in theory."""
    from app.database import Base

    for table in Base.metadata.tables.values():
        for column in table.columns:
            if column.name in REDACTED_COLUMNS:
                assert column.info.get("export") == "redact", (
                    f"{table.name}.{column.name} is redacted only by its name; "
                    "add info={'export': 'redact'} so it survives a rename"
                )
