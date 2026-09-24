"""A minimal fake standing in for the `supabase` client's fluent
query-builder API (`.table(...).select(...).eq(...).single().execute()`
etc.), just enough to exercise app.main's Supabase call patterns in tests
without hitting a real project.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FakeResponse:
    data: object


class FakeTable:
    def __init__(self, name: str, client: "FakeSupabase"):
        self.name = name
        self.client = client
        self.op: str | None = None
        self.payload: dict | None = None
        self.filters: dict = {}
        self.is_single = False

    def select(self, *_args, **_kwargs):
        self.op = "select"
        return self

    def insert(self, data: dict):
        self.op = "insert"
        self.payload = data
        return self

    def update(self, data: dict):
        self.op = "update"
        self.payload = data
        return self

    def eq(self, field_name: str, value):
        self.filters[field_name] = value
        return self

    def order(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def single(self):
        self.is_single = True
        return self

    def _matching_rows(self) -> list[dict]:
        rows = self.client.data.get(self.name, [])
        return [r for r in rows if all(r.get(k) == v for k, v in self.filters.items())]

    def execute(self) -> FakeResponse:
        if self.op == "select":
            matched = self._matching_rows()
            if self.is_single:
                return FakeResponse(data=matched[0] if matched else None)
            return FakeResponse(data=matched)
        if self.op == "insert":
            self.client.calls.append(("insert", self.name, self.payload))
            self.client.data.setdefault(self.name, []).append(dict(self.payload))
            return FakeResponse(data=[self.payload])
        if self.op == "update":
            self.client.calls.append(("update", self.name, self.payload, dict(self.filters)))
            for row in self._matching_rows():
                row.update(self.payload)
            return FakeResponse(data=None)
        raise AssertionError("FakeTable.execute() called without select/insert/update first")


class _FakeAdmin:
    def __init__(self, client: "FakeSupabase"):
        self._client = client

    def delete_user(self, user_id: str) -> None:
        self._client.calls.append(("auth.admin.delete_user", user_id))


class _FakeAuth:
    def __init__(self, client: "FakeSupabase"):
        self.admin = _FakeAdmin(client)


@dataclass
class FakeSupabase:
    data: dict = field(default_factory=dict)
    calls: list = field(default_factory=list)

    def __post_init__(self):
        self.auth = _FakeAuth(self)

    def table(self, name: str) -> FakeTable:
        return FakeTable(name, self)
