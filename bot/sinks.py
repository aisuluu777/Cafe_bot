"""Куда отправляются заказы. Для POS — реализуй OrderSink и добавь в список sinks."""
from html import escape
from typing import Protocol

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from .config import Config
from .menu import CURRENCY
from .storage import Order


class OrderSink(Protocol):
    async def send(self, order: Order) -> None: ...


def format_order(order: Order, station: str | None = None, with_total: bool = True) -> str:
    titles = {"bar": "☕ БАР", "kitchen": "🍳 КУХНЯ"}
    lines = [l for l in order.lines if station in (None, l[3])]
    head = f"🧾 <b>Заказ №{order.id}</b>" + (f" — {titles[station]}" if station else "")
    text = [head, f"📍 {escape(order.place)}", f"👤 {escape(order.customer)}", ""]
    text += [f"• {escape(n)} × {q}" for n, q, _, _ in lines]
    if order.comment:
        text += ["", f"💬 {escape(order.comment)}"]
    if with_total:
        text += ["", f"Итого: <b>{order.total} {CURRENCY}</b>"]
    return "\n".join(text)


class TelegramSink:
    """Шлёт заказ в чат(ы) сотрудников, разделяя позиции по станциям (бар/кухня)."""

    def __init__(self, bot: Bot, cfg: Config):
        self.bot, self.cfg = bot, cfg

    def _chat_for(self, station: str) -> int:
        return (self.cfg.bar_chat_id if station == "bar" else self.cfg.kitchen_chat_id) or self.cfg.staff_chat_id

    async def send(self, order: Order) -> None:
        stations = {l[3] for l in order.lines}
        # Если все станции в одном чате — одно сообщение целиком, иначе по сообщению на станцию
        chats = {s: self._chat_for(s) for s in stations}
        if len(set(chats.values())) == 1 and len(stations) > 1:
            groups = [(None, next(iter(chats.values())))]
        else:
            groups = [(s, c) for s, c in chats.items()]
        for station, chat in groups:
            kb = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="👨‍🍳 Принял", callback_data=f"st:{order.id}:accepted"),
                InlineKeyboardButton(text="✅ Готово", callback_data=f"st:{order.id}:ready"),
            ]])
            await self.bot.send_message(chat, format_order(order, station), reply_markup=kb)


class PosSink:
    """Заглушка под POS-терминал: реализуй HTTP/API-вызов своей кассы."""

    async def send(self, order: Order) -> None:
        # payload = {"id": order.id, "items": [...], "total": order.total}
        # async with aiohttp.ClientSession() as s: await s.post(POS_URL, json=payload)
        pass
