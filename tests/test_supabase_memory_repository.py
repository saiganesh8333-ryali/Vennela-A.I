from datetime import datetime, timezone

from memory import MemoryCategory, MemoryDomain, MemoryRecord, MemoryStatus
from memory.repository import SupabaseMemoryRepository


class Response:
    def __init__(self, data):
        self.data = data
        self.error = None


class Query:
    def __init__(self, table):
        self.table = table
        self.filters = {}
        self.operation = "select"
        self.payload = None

    def select(self, *_):
        self.operation = "select"
        return self

    def insert(self, payload):
        self.operation, self.payload = "insert", payload
        return self

    def update(self, payload):
        self.operation, self.payload = "update", payload
        return self

    def eq(self, key, value):
        self.filters[key] = value
        return self

    def order(self, *_args, **_kwargs):
        return self

    def limit(self, *_args):
        return self

    def execute(self):
        rows = [
            row for row in self.table.rows
            if all(row.get(key) == value for key, value in self.filters.items())
        ]
        if self.operation == "insert":
            self.table.rows.append(dict(self.payload))
            rows = [self.table.rows[-1]]
        elif self.operation == "update":
            for row in rows:
                row.update(self.payload)
            rows = [dict(row) for row in rows]
        return Response(rows)


class Table:
    def __init__(self):
        self.rows = []

    def table(self, *_):
        return self

    def select(self, *args):
        return Query(self).select(*args)

    def insert(self, payload):
        return Query(self).insert(payload)

    def update(self, payload):
        return Query(self).update(payload)


class Client:
    def __init__(self):
        self.memory_table = Table()

    def table(self, name):
        assert name == "memories"
        return self.memory_table


def record(**changes):
    values = dict(
        memory_id="m1",
        owner_id="boss",
        domain=MemoryDomain.BOSS_PERSONAL,
        category=MemoryCategory.FACT,
        content={"text": "robotics"},
        source="conversation",
        confidence=0.8,
        importance=0.7,
        status=MemoryStatus.ACTIVE,
        created_at=datetime.now(timezone.utc),
        embedding=[0.1, 0.2],
        expires_at="2026-09-08T00:00:00Z",
        metadata={"topic": "technology"},
    )
    values.update(changes)
    return MemoryRecord(**values)


def test_supabase_repository_round_trip_and_lifecycle():
    client = Client()
    repository = SupabaseMemoryRepository(client)
    stored = repository.create(record())
    assert stored.content == {"text": "robotics"}
    assert stored.embedding == [0.1, 0.2]
    assert stored.expires_at.tzinfo is timezone.utc
    assert repository.get("m1").metadata == {"topic": "technology"}
    assert [item.memory_id for item in repository.list("boss", MemoryDomain.BOSS_PERSONAL)] == ["m1"]
    assert repository.list("other", MemoryDomain.BOSS_PERSONAL) == []
    assert repository.transition_status("m1", MemoryStatus.DELETED).status is MemoryStatus.DELETED
    assert repository.list("boss", MemoryDomain.BOSS_PERSONAL) == []
