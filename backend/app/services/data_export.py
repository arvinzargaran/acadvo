"""Assemble everything the database holds about one account.

PIPEDA Principle 9 (Individual Access) gives a person the right to a copy of the
personal information an organization holds about them, in an understandable
form. `DELETE /users/me` already discharges the deletion side; this is the read
side of the same obligation.

**Why this walks the schema instead of listing tables.**

The obvious implementation — a function that selects from conversations, then
courses, then projects, and so on — is correct exactly once. The next feature
adds a table, nobody remembers this file, and the export silently starts
under-reporting. That failure is invisible: the export still succeeds, still
looks complete, and the omission only surfaces when a student asks for their
data and does not get all of it.

So the set of tables is derived from the foreign keys instead. Anything that
points at `users.id`, plus anything that reaches `users.id` through one of
those, is in the export by construction — the same reachability the delete
cascade relies on. `test_data_export.py` asserts that equivalence, so a new
user-owned table joins both or fails the suite.

**Why the graph walk is written for schemas we do not have yet.**

The point of deriving the table set is that the next schema change is handled
without anyone editing this file. That only holds if the walk copes with the
shapes a schema change can introduce: a composite primary key, a foreign key
aimed at a unique column that is not the primary key, two independent paths
from the same table back to `users`, a self-reference, and a nullable link.
Each of those, handled naively, either drops rows from an export or — the one
outcome this file must never have — scopes a table on a predicate that can
match another account's rows. The helpers below are written and tested against
a synthetic schema containing all of them, not just against the tables that
happen to exist today.
"""
from __future__ import annotations

import datetime as dt
import decimal
import enum
import uuid
from typing import Any, Iterable

from sqlalchemy import ForeignKey, MetaData, Table, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import Base

ROOT_TABLE = "users"

# Columns that are credentials rather than personal information. A copy of the
# password hash or of a live session/feed token tells the account holder nothing
# they do not already know, and turns one intercepted export into account
# takeover — including for the calendar feed, whose token is a permanent bearer
# credential. The keys stay in the output, marked, so the export is honest about
# what exists rather than quietly shaped.
REDACTED_COLUMNS = frozenset(
    {
        "hashed_password",
        "calendar_token",
        "token",
        "token_hash",
        "refresh_token",
    }
)

REDACTED_PLACEHOLDER = "[redacted: security credential, not exported]"

# An export is one request holding one connection while it reads every
# user-owned table with no `LIMIT`. Row counts here are driven by user actions
# (study sessions, messages, assessments), so "how big can this get" is not
# bounded by anything except how long an account has existed — and an account
# that has ground out a few hundred thousand rows can make this endpoint read
# them all into memory, serialise them, and hold a worker for the duration,
# five times an hour. The cap turns that into a large-but-finite response.
#
# It also keeps the scoping `IN (...)` lists below Postgres' 65535 bind
# parameter ceiling: without a cap, a child table's query would not merely be
# slow, it would fail outright once a parent exceeded that many rows.
MAX_ROWS_PER_TABLE = 25_000


def _user_owned_tables(
    metadata: MetaData | None = None, root: str = ROOT_TABLE
) -> dict[str, Table]:
    """Every table reachable from `root` by foreign key.

    Two passes is enough for the current schema (assessments -> courses -> users
    is the deepest chain), but the loop runs to a fixed point so a deeper chain
    added later is still caught.
    """
    metadata = metadata if metadata is not None else Base.metadata
    tables = {name: t for name, t in metadata.tables.items() if name != root}
    owned: dict[str, Table] = {}
    frontier = {root}

    while frontier:
        next_frontier: set[str] = set()
        for name, table in tables.items():
            if name in owned:
                continue
            if any(fk.column.table.name in frontier for fk in table.foreign_keys):
                owned[name] = table
                next_frontier.add(name)
        frontier = next_frontier

    return owned


def _scoping_candidates(
    table: Table, collected: Iterable[str], root: str = ROOT_TABLE
) -> list[ForeignKey]:
    """Foreign keys of `table` usable to scope it to one account, best first.

    `table.foreign_keys` is a set, so "the first usable one" would scope a table
    differently between runs. The order here is fixed and meaningful:

    1. A NOT NULL link beats a nullable one, even when the nullable one points
       straight at `root`. Scoping on a nullable column silently drops every row
       where it is NULL, and every candidate here leads back to the same
       account, so the mandatory link is the one that returns all of them.
       Concretely: scope `courses` on `requirement_bucket_id` (which is
       `ON DELETE SET NULL`) and every course the student has not filed under a
       requirement vanishes from their export.
    2. Among equally mandatory links, a direct one to `root` beats an indirect
       one — shortest path, fewest parents whose own scoping has to be right.
    3. Column name, purely so the result is stable.

    A self-reference is never a candidate: a table's own ids are not collected
    until after it is read, so scoping on them would return nothing.
    """
    collected = set(collected)
    return sorted(
        (
            fk
            for fk in table.foreign_keys
            if fk.column.table.name in collected and fk.column.table.name != table.name
        ),
        key=lambda fk: (
            bool(fk.parent.nullable),
            fk.column.table.name != root,
            fk.parent.name,
        ),
    )


def _jsonable(value: Any) -> Any:
    """Render a database value as something `json.dumps` accepts.

    Decimal becomes a string, not a float: grades and GPAs are exactly the
    numbers where binary floating point would hand someone back a 3.6699999.
    """
    if value is None or isinstance(value, bool):
        return value
    # Enums first: every status enum in this schema is a `str, enum.Enum`, so an
    # `isinstance(value, str)` test matches them and hands the member object
    # back instead of its value. `json.dumps` papers over that, but anything
    # else that touches the payload (a different serialiser, a comparison, a
    # test) sees `CourseStatus.completed` where the export promises a string.
    if isinstance(value, enum.Enum):
        return _jsonable(value.value)
    if isinstance(value, str):
        return str(value)
    if isinstance(value, int):
        return value
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, (dt.datetime, dt.date, dt.time)):
        return value.isoformat()
    if isinstance(value, decimal.Decimal):
        return str(value)
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (bytes, bytearray)):
        return f"[{len(value)} bytes, not exported]"
    return str(value)


def _is_redacted(column) -> bool:
    """Whether a column holds a credential rather than personal information.

    Two sources, and the marker is the one that matters. This file's whole
    design is that a new table joins the export automatically without anyone
    reading this module — which means a future `otp_secret` or `api_key` column
    would join it automatically too, unredacted, because a name list is the one
    property that does not auto-extend. `info={"export": "redact"}` on the model
    puts the decision next to the column it protects, where the person adding a
    credential is already looking. The name list stays as a backstop for columns
    that predate the marker.
    """
    return column.info.get("export") == "redact" or column.name in REDACTED_COLUMNS


def _row_to_dict(table: Table, row) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for column in table.columns:
        raw = row._mapping[column]
        out[column.name] = REDACTED_PLACEHOLDER if _is_redacted(column) else _jsonable(raw)
    return out


def _referenced_columns(metadata: MetaData) -> set[tuple[str, str]]:
    """Every `(table, column)` some foreign key in the schema points at.

    Not "every primary key": a foreign key is free to reference any unique
    column, and a composite primary key has no single "the" id. Collecting the
    columns that are actually referenced is what lets the scoping predicate
    below compare like with like instead of assuming the first primary key
    column is the join target.
    """
    return {
        (fk.column.table.name, fk.column.name)
        for table in metadata.tables.values()
        for fk in table.foreign_keys
    }


async def _rows_for(
    db: AsyncSession,
    table: Table,
    collected: set[str],
    collected_values: dict[tuple[str, str], set],
    root: str = ROOT_TABLE,
) -> tuple[list, bool]:
    """Rows of `table` belonging to this account, scoped through its parent.

    Returns the rows and whether the read hit `MAX_ROWS_PER_TABLE`.

    A table is filtered on the best foreign key it has (see
    `_scoping_candidates`), against the values already collected for *the exact
    parent column that key references*. Nothing is selected without a scoping
    predicate — an unfiltered branch here would put another student's rows in
    this student's export, which is the one bug this file must never have.
    """
    predicate = None
    for fk in _scoping_candidates(table, collected, root):
        values = collected_values.get((fk.column.table.name, fk.column.name))
        if not values:
            # The parent has no rows for this account, so neither can the child.
            # Returning [] is right; falling through to a weaker key would not
            # be, and falling through to no key at all would be a leak.
            return [], False
        predicate = table.c[fk.parent.name].in_(values)
        break

    if predicate is None:  # pragma: no cover - the caller only passes ready tables
        return [], False

    stmt = select(table).where(predicate)
    if table.primary_key.columns:
        # Deterministic order, so a truncated export is reproducible rather than
        # whatever the planner felt like returning.
        stmt = stmt.order_by(*table.primary_key.columns)
    result = await db.execute(stmt.limit(MAX_ROWS_PER_TABLE + 1))
    rows = result.fetchall()
    if len(rows) > MAX_ROWS_PER_TABLE:
        return rows[:MAX_ROWS_PER_TABLE], True
    return rows, False


def _collect_values(
    table: Table,
    rows: list,
    referenced: set[tuple[str, str]],
    collected_values: dict[tuple[str, str], set],
) -> None:
    """Remember the raw values children will scope themselves against.

    Raw values, not the serialised ones: these go straight back into a
    `WHERE ... IN`, and a UUID stringified on the way through no longer binds
    against a UUID column. NULLs are dropped — `IN (NULL)` matches nothing and
    only bloats the parameter list.
    """
    for column in table.columns:
        key = (table.name, column.name)
        if key not in referenced:
            continue
        collected_values[key] = {
            row._mapping[column] for row in rows if row._mapping[column] is not None
        }


async def export_user_data(
    db: AsyncSession,
    user_id: uuid.UUID,
    metadata: MetaData | None = None,
    root: str = ROOT_TABLE,
) -> dict[str, Any]:
    """Everything stored about `user_id`, as a JSON-serialisable document."""
    metadata = metadata if metadata is not None else Base.metadata
    users_table = metadata.tables[root]
    pk = list(users_table.primary_key.columns)[0]
    result = await db.execute(select(users_table).where(pk == user_id))
    account_row = result.fetchone()
    if account_row is None:  # pragma: no cover - the caller is an authenticated user
        raise LookupError("user not found")

    referenced = _referenced_columns(metadata)
    collected_values: dict[tuple[str, str], set] = {}
    _collect_values(users_table, [account_row], referenced, collected_values)
    collected: set[str] = {root}

    tables: dict[str, list[dict[str, Any]]] = {}
    truncated: list[str] = []

    owned = _user_owned_tables(metadata, root)
    owned_names = set(owned) | {root}
    remaining = dict(owned)
    # Parents before children, so a child's scoping ids already exist. A table is
    # only read once *every* user-owned parent it has is collected: reading it as
    # soon as any one parent is ready makes the choice of scoping key depend on
    # dictionary order, which is how a table ends up scoped on a nullable link
    # on one run and a NOT NULL one on the next.
    strict = True
    while remaining:
        progressed = False
        for name, table in sorted(remaining.items()):
            parents = {
                fk.column.table.name for fk in table.foreign_keys if fk.column.table.name != name
            } & owned_names
            if not parents:  # pragma: no cover - owned means it has such a parent
                del remaining[name]
                continue
            if strict:
                if not parents <= collected:
                    continue
            elif not parents & collected:
                continue
            rows, was_truncated = await _rows_for(db, table, collected, collected_values, root)
            tables[name] = [_row_to_dict(table, row) for row in rows]
            # A child scoped through a truncated parent is truncated too, even
            # though its own read never hit the cap: it was only ever offered the
            # parent ids that survived. Reporting the parent alone would let the
            # child's rows read as a complete set — an export that silently
            # understates is the failure this whole module exists to avoid.
            if was_truncated or (parents & set(truncated)):
                truncated.append(name)
            _collect_values(table, rows, referenced, collected_values)
            collected.add(name)
            del remaining[name]
            progressed = True
        if not progressed:
            if strict:
                # A cycle in the ownership graph (or a table whose only parents
                # are in that cycle) would otherwise strand rows out of the
                # export entirely. Scoping on a partially-collected parent still
                # cannot leak — every collected parent is already account-scoped
                # — so relaxing is safe, and under-reporting is the failure this
                # file exists to avoid.
                strict = False
                continue
            break  # pragma: no cover - unreachable while every owned table has a parent

    return {
        "export_format": "acadvo-account-export/1",
        "exported_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "notice": (
            "This file contains the personal information acadvo holds about your "
            "account, as it exists at the time of export. Security credentials "
            "(password hash, session and calendar-feed tokens) are marked as "
            "redacted rather than included. Course catalogue and program "
            "requirement data is shared reference material, not personal "
            "information, and is not included."
        ),
        # Named rather than silent: an export that quietly stopped at 25,000 rows
        # is not an answer to "give me my data", so the document says which
        # tables were cut and how far.
        "truncated_tables": sorted(truncated),
        "max_rows_per_table": MAX_ROWS_PER_TABLE,
        "account": _row_to_dict(users_table, account_row),
        "tables": tables,
    }
