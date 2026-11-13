"""Хранение заказов в SQLite (stdlib, обёрнуто в to_thread)."""
import asyncio
import json
import sqlite3
from dataclasses import dataclass, field


@dataclass
class Order:
    id: int
    user_id: int
    customer: str
    place: str  # "Стол 5" / "С собой"
    comment: str
    lines: list[tuple[str, int, int, str]] = field(default_factory=list)  # (name, qty, price, station)

    @property
    def total(self) -> int:
        return sum(q * p for _, q, p, _ in self.lines)


class Storage:
    def __init__(self, path: str = "orders.db"):
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS orders ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, customer TEXT,"
            "place TEXT, comment TEXT, lines TEXT, status TEXT DEFAULT 'new',"
            "created_at TEXT DEFAULT CURRENT_TIMESTAMP)"
        )
        self._db.commit()

    def _create(self, user_id, customer, place, comment, lines) -> int:
        cur = self._db.execute(
            "INSERT INTO orders (user_id, customer, place, comment, lines) VALUES (?,?,?,?,?)",
            (user_id, customer, place, comment, json.dumps(lines, ensure_ascii=False)),
        )
        self._db.commit()
        return cur.lastrowid

    async def create_order(self, user_id, customer, place, comment, lines) -> Order:
        oid = await asyncio.to_thread(self._create, user_id, customer, place, comment, lines)
        return Order(oid, user_id, customer, place, comment, lines)

    def _set_status(self, oid: int, status: str):
        self._db.execute("UPDATE orders SET status=? WHERE id=?", (status, oid))
        self._db.commit()

    async def set_status(self, oid: int, status: str):
        await asyncio.to_thread(self._set_status, oid, status)

    def _get_user_id(self, oid: int) -> int | None:
        row = self._db.execute("SELECT user_id FROM orders WHERE id=?", (oid,)).fetchone()
        return row[0] if row else None

    async def get_user_id(self, oid: int) -> int | None:
        return await asyncio.to_thread(self._get_user_id, oid)
