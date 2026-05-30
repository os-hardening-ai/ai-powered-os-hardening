"""
Tests for api.auth_store (SQLite user store + bcrypt).

Isolated temp DB per test. Covers password hashing/verification, CRUD, duplicate
guard, credential verification, and idempotent seeding (dev/prod).
"""

from __future__ import annotations

import pytest

from api import db
from api.auth_models import Role
from api.auth_store import UserStore, hash_password, verify_password


@pytest.fixture
def store(tmp_path):
    db.reset_for_tests(str(tmp_path / "auth.db"))
    try:
        yield UserStore()
    finally:
        db.reset_for_tests("data/auth.db")


class TestPasswordHash:
    def test_hash_is_not_plaintext(self):
        h = hash_password("s3cret")
        assert h != "s3cret" and h.startswith("$2")

    def test_verify_correct(self):
        h = hash_password("hunter2")
        assert verify_password("hunter2", h) is True

    def test_verify_wrong(self):
        h = hash_password("hunter2")
        assert verify_password("nope", h) is False

    def test_verify_bad_hash_returns_false(self):
        assert verify_password("x", "not-a-hash") is False


class TestCRUD:
    def test_create_and_get(self, store):
        store.create("alice", "pw", Role.SECURITY)
        rec = store.get("alice")
        assert rec["username"] == "alice" and rec["role"] == "security"
        assert "pw" not in rec["password_hash"]

    def test_duplicate_rejected(self, store):
        store.create("bob", "pw", Role.DEVELOPER)
        with pytest.raises(ValueError):
            store.create("bob", "pw2", Role.SYSADMIN)

    def test_count_and_list(self, store):
        assert store.count() == 0
        store.create("a", "p", Role.END_USER)
        store.create("b", "p", Role.END_USER)
        assert store.count() == 2
        assert {u["username"] for u in store.list_users()} == {"a", "b"}


class TestVerifyCredentials:
    def test_valid_returns_role(self, store):
        store.create("carol", "pw", Role.SYSADMIN)
        assert store.verify_credentials("carol", "pw") == Role.SYSADMIN

    def test_wrong_password_none(self, store):
        store.create("dave", "pw", Role.DEVELOPER)
        assert store.verify_credentials("dave", "WRONG") is None

    def test_unknown_user_none(self, store):
        assert store.verify_credentials("ghost", "pw") is None


class TestSeeding:
    def test_dev_seeds_four_roles(self, store):
        created = store.seed_defaults(dev_mode=True)
        roles = {role for _, _, role in created}
        assert roles == {"sysadmin", "security", "developer", "end_user"}
        assert store.count() == 4

    def test_prod_seeds_only_admin(self, store):
        created = store.seed_defaults(dev_mode=False)
        assert len(created) == 1 and created[0][0] == "admin" and created[0][2] == "sysadmin"

    def test_seed_idempotent(self, store):
        store.seed_defaults(dev_mode=True)
        assert store.seed_defaults(dev_mode=True) == []  # tablo dolu → no-op
        assert store.count() == 4
