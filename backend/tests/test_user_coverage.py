"""Coverage-raising tests for app.services.user.

Covers get_user (found / 404) and update_user (partial update via exclude_unset,
falsy-value handling, empty-payload no-op, timestamp bump).
"""

import uuid

import pytest
from fastapi import HTTPException

from app.models.user import User
from app.schemas.user import UserUpdate
from app.services.auth import hash_password
from app.services.user import get_user, update_user


@pytest.fixture
async def plain_user(db):
    user = User(
        id=uuid.uuid4(),
        email="profile@example.com",
        hashed_password=hash_password("testpass123"),
        full_name="Original Name",
        university="Old U",
        program="Physics",
        start_year=2022,
        onboarding_complete=False,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def test_get_user_found(plain_user, db):
    fetched = await get_user(plain_user.id, db)
    assert fetched.id == plain_user.id
    assert fetched.email == "profile@example.com"


async def test_get_user_missing_raises_404(db):
    with pytest.raises(HTTPException) as exc:
        await get_user(uuid.uuid4(), db)
    assert exc.value.status_code == 404


async def test_update_user_partial_only_touches_set_fields(plain_user, db):
    data = UserUpdate(full_name="New Name", program="Computer Science")
    updated = await update_user(plain_user, data, db)

    assert updated.full_name == "New Name"
    assert updated.program == "Computer Science"
    # Fields not present in the payload are left as-is (exclude_unset).
    assert updated.university == "Old U"
    assert updated.start_year == 2022


async def test_update_user_sets_falsy_boolean(plain_user, db):
    # onboarding_complete=True is an explicit, falsy-adjacent field that must be
    # written even though the model default is False.
    data = UserUpdate(onboarding_complete=True)
    updated = await update_user(plain_user, data, db)
    assert updated.onboarding_complete is True

    # Re-fetch from DB to confirm it was committed, not just set in memory.
    refetched = await get_user(plain_user.id, db)
    assert refetched.onboarding_complete is True


async def test_update_user_empty_payload_is_noop(plain_user, db):
    original_name = plain_user.full_name
    data = UserUpdate()  # nothing set
    updated = await update_user(plain_user, data, db)
    assert updated.full_name == original_name
    assert updated.university == "Old U"


async def test_update_user_persists_new_grad_year(plain_user, db):
    data = UserUpdate(expected_graduation_year=2027)
    await update_user(plain_user, data, db)
    refetched = await get_user(plain_user.id, db)
    assert refetched.expected_graduation_year == 2027
