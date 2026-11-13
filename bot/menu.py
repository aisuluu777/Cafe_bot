"""Меню хранится в SQLite и редактируется админом. SEED — стартовое наполнение при первом запуске.
station: 'bar' (бариста) или 'kitchen' (повара) — определяет, куда уйдёт позиция."""
import sqlite3
from dataclasses import dataclass

CURRENCY = "сом"
STATIONS = {"bar": "☕ Бар", "kitchen": "🍳 Кухня"}


@dataclass(frozen=True)
class Item:
    id: int
    cat_id: str
    name: str
    price: int
    station: str
    photo: str | None  # Telegram file_id
    available: bool


@dataclass(frozen=True)
class Category:
    id: str
    title: str


SEED = (
    ("coffee", "☕ Кофе", (
        ("Эспрессо", 120, "bar"), ("Американо", 140, "bar"), ("Капучино", 190, "bar"),
        ("Латте", 210, "bar"), ("Флэт уайт", 230, "bar"),
    )),
    ("drinks", "🥤 Напитки", (
        ("Чай (чайник)", 150, "bar"), ("Лимонад", 180, "bar"), ("Сок", 130, "bar"),
    )),
    ("food", "🍳 Еда", (
        ("Омлет", 250, "kitchen"), ("Цезарь с курицей", 350, "kitchen"),
        ("Бургер", 420, "kitchen"), ("Паста карбонара", 380, "kitchen"),
    )),
    ("desserts", "🍰 Десерты", (
        ("Чизкейк", 220, "kitchen"), ("Круассан", 130, "kitchen"),
    )),
)

_EDITABLE = {"name", "price", "station", "photo", "available"}


class Menu:
    def __init__(self, path: str = "orders.db"):
        self._db = sqlite3.connect(path)
        self._db.executescript(
            "CREATE TABLE IF NOT EXISTS categories (id TEXT PRIMARY KEY, title TEXT, sort INTEGER);"
            "CREATE TABLE IF NOT EXISTS items (id INTEGER PRIMARY KEY AUTOINCREMENT, cat_id TEXT,"
            " name TEXT, price INTEGER, station TEXT, photo TEXT, available INTEGER DEFAULT 1);"
        )
        if not self._db.execute("SELECT 1 FROM categories").fetchone():
            for n, (cid, title, items) in enumerate(SEED):
                self._db.execute("INSERT INTO categories VALUES (?,?,?)", (cid, title, n))
                for name, price, station in items:
                    self._db.execute(
                        "INSERT INTO items (cat_id, name, price, station) VALUES (?,?,?,?)",
                        (cid, name, price, station),
                    )
            self._db.commit()

    @staticmethod
    def _item(r) -> Item:
        return Item(r[0], r[1], r[2], r[3], r[4], r[5], bool(r[6]))

    _COLS = "id, cat_id, name, price, station, photo, available"

    def categories(self) -> list[Category]:
        return [Category(*r) for r in self._db.execute("SELECT id, title FROM categories ORDER BY sort")]

    def category(self, cat_id: str) -> Category | None:
        r = self._db.execute("SELECT id, title FROM categories WHERE id=?", (cat_id,)).fetchone()
        return Category(*r) if r else None

    def items(self, cat_id: str) -> list[Item]:
        rows = self._db.execute(f"SELECT {self._COLS} FROM items WHERE cat_id=? ORDER BY id", (cat_id,))
        return [self._item(r) for r in rows]

    def item(self, item_id: int) -> Item | None:
        r = self._db.execute(f"SELECT {self._COLS} FROM items WHERE id=?", (item_id,)).fetchone()
        return self._item(r) if r else None

    def add_item(self, cat_id: str, name: str, price: int, station: str, photo: str | None) -> int:
        cur = self._db.execute(
            "INSERT INTO items (cat_id, name, price, station, photo) VALUES (?,?,?,?,?)",
            (cat_id, name, price, station, photo),
        )
        self._db.commit()
        return cur.lastrowid

    def update_item(self, item_id: int, field: str, value) -> None:
        if field not in _EDITABLE:
            raise ValueError(field)
        self._db.execute(f"UPDATE items SET {field}=? WHERE id=?", (value, item_id))
        self._db.commit()

    def delete_item(self, item_id: int) -> None:
        self._db.execute("DELETE FROM items WHERE id=?", (item_id,))
        self._db.commit()
