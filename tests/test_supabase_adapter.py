import pytest

from memory.adapters import supabase_adapter


class FakeResponse:
    def __init__(self, data=None, error=None, status_code=200):
        self.data = data or []
        self.error = error
        self.status_code = status_code


class FakeQuery:
    def __init__(self, client, operation, data=None):
        self.client = client
        self.operation = operation
        self.data = data
        self.filters = []
        self.limit_value = None

    def select(self, columns):
        self.client.selects.append(columns)
        return self

    def eq(self, column, value):
        self.filters.append((column, value))
        return self

    def limit(self, value):
        self.limit_value = value
        return self

    def upsert(self, payload, on_conflict=None):
        self.client.upserts.append((payload, on_conflict))
        self.client.rows = [
            row for row in self.client.rows if row.get("user_id") != payload["user_id"]
        ]
        self.client.rows.append(payload)
        return self

    def delete(self):
        self.client.deletes += 1
        self.operation = "delete"
        return self

    def execute(self):
        if self.operation == "select":
            rows = self.client.rows
            for column, value in self.filters:
                rows = [row for row in rows if row.get(column) == value]
            if self.limit_value is not None:
                rows = rows[: self.limit_value]
            return FakeResponse(rows)
        if self.operation == "delete":
            for column, value in self.filters:
                self.client.rows = [
                    row for row in self.client.rows if row.get(column) != value
                ]
            return FakeResponse([])
        return FakeResponse([])


class FakeClient:
    def __init__(self, rows=None):
        self.rows = list(rows or [])
        self.selects = []
        self.filters = []
        self.limits = []
        self.upserts = []
        self.deletes = 0

    def table(self, name):
        assert name == "memories"
        return FakeQuery(self, "select")


@pytest.fixture
def fake_client(monkeypatch):
    client = FakeClient()
    monkeypatch.setenv("SUPABASE_URL", "https://example.test")
    monkeypatch.setenv("SUPABASE_KEY", "test-key")
    monkeypatch.setattr(supabase_adapter, "_client", lambda: client)
    return client


def test_missing_user_returns_default(monkeypatch):
    monkeypatch.setattr(supabase_adapter, "_client", lambda: FakeClient())
    assert supabase_adapter.load_memory("missing") == supabase_adapter._default_memory()


def test_save_maps_canonical_payload_and_repeated_save_upserts(fake_client):
    data = {"long_term": ["first memory"], "summary": "summary"}
    assert supabase_adapter.save_memory("user-1", data)
    assert fake_client.upserts[-1][1] == "user_id"
    assert fake_client.rows[0]["long_term"][0]["text"] == "first memory"
    assert supabase_adapter.save_memory("user-1", {"summary": "updated"})
    assert len(fake_client.rows) == 1
    assert fake_client.rows[0]["long_term"][0]["text"] == "first memory"
    assert fake_client.rows[0]["summary"] == "updated"


def test_load_normalizes_legacy_long_term(fake_client):
    fake_client.rows.append({"user_id": "user-2", "long_term": ["legacy"]})
    memory = supabase_adapter.load_memory("user-2")
    assert memory["long_term"] == [
        {"text": "legacy", "timestamp": None, "importance": 0.0}
    ]


def test_delete_and_list_user_ids(fake_client):
    fake_client.rows.extend([{"user_id": "a"}, {"user_id": "b"}])
    assert sorted(supabase_adapter.list_user_ids()) == ["a", "b"]
    assert supabase_adapter.delete_memory("a")
    assert [row["user_id"] for row in fake_client.rows] == ["b"]


def test_missing_configuration_fails_clearly(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_KEY", raising=False)
    with pytest.raises(supabase_adapter.SupabaseConfigurationError, match="SUPABASE_URL"):
        supabase_adapter.load_memory("user")
