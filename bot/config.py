import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _int(name: str) -> int | None:
    v = os.getenv(name, "").strip()
    return int(v) if v else None


@dataclass(frozen=True)
class Config:
    token: str
    staff_chat_id: int
    bar_chat_id: int | None
    kitchen_chat_id: int | None
    admin_ids: frozenset[int]


def load_config() -> Config:
    return Config(
        token=os.environ["BOT_TOKEN"],
        staff_chat_id=int(os.environ["STAFF_CHAT_ID"]),
        bar_chat_id=_int("BAR_CHAT_ID"),
        kitchen_chat_id=_int("KITCHEN_CHAT_ID"),
        admin_ids=frozenset(int(x) for x in os.getenv("ADMIN_IDS", "").replace(" ", "").split(",") if x),
    )
