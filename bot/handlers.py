from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from .menu import CURRENCY, Menu
from .sinks import OrderSink
from .storage import Storage
from .ui import show

router = Router()


class Checkout(StatesGroup):
    place = State()
    comment = State()


# ---------- helpers ----------
async def get_cart(state: FSMContext, menu: Menu) -> dict[str, int]:
    """Корзина {item_id: qty}; позиции, удалённые из меню, выбрасываются."""
    cart = (await state.get_data()).get("cart", {})
    valid = {i: q for i, q in cart.items() if menu.item(int(i))}
    if valid != cart:
        await state.update_data(cart=valid)
    return valid


def cart_total(cart: dict[str, int], menu: Menu) -> int:
    return sum(menu.item(int(i)).price * q for i, q in cart.items())


def cart_text(cart: dict[str, int], menu: Menu) -> str:
    if not cart:
        return "🛒 Корзина пуста"
    lines = []
    for i, q in cart.items():
        it = menu.item(int(i))
        lines.append(f"• {it.name} × {q} = {it.price * q} {CURRENCY}")
    return "🛒 <b>Ваш заказ:</b>\n" + "\n".join(lines) + f"\n\nИтого: <b>{cart_total(cart, menu)} {CURRENCY}</b>"


def cart_btn(cart: dict[str, int]) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=f"🛒 Корзина ({sum(cart.values())})", callback_data="cart")


def main_kb(cart: dict[str, int], menu: Menu) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for c in menu.categories():
        b.button(text=c.title, callback_data=f"cat:{c.id}")
    b.adjust(2)
    if cart:
        b.row(cart_btn(cart))
    return b.as_markup()


def cat_kb(cat_id: str, cart: dict[str, int], menu: Menu) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for it in menu.items(cat_id):
        if it.available:
            b.button(text=f"{'📷 ' if it.photo else ''}{it.name} — {it.price} {CURRENCY}", callback_data=f"item:{it.id}")
        else:
            b.button(text=f"❌ {it.name} (нет в наличии)", callback_data="noop")
    b.adjust(1)
    row = [InlineKeyboardButton(text="⬅️ Меню", callback_data="menu")]
    if cart:
        row.append(cart_btn(cart))
    b.row(*row)
    return b.as_markup()


def item_card(item_id: int, cart: dict[str, int], menu: Menu):
    it = menu.item(item_id)
    n = cart.get(str(item_id), 0)
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text=f"➕ В корзину{f' ({n})' if n else ''}", callback_data=f"add:{item_id}"))
    row = [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"cat:{it.cat_id}")]
    if cart:
        row.append(cart_btn(cart))
    b.row(*row)
    return f"<b>{it.name}</b>\n{it.price} {CURRENCY}", b.as_markup(), it.photo


def cart_kb(cart: dict[str, int], menu: Menu) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for iid, q in cart.items():
        b.row(
            InlineKeyboardButton(text="➖", callback_data=f"dec:{iid}"),
            InlineKeyboardButton(text=f"{menu.item(int(iid)).name} × {q}", callback_data="noop"),
            InlineKeyboardButton(text="➕", callback_data=f"add_c:{iid}"),
        )
    if cart:
        b.row(InlineKeyboardButton(text="✅ Оформить", callback_data="checkout"))
        b.row(InlineKeyboardButton(text="🗑 Очистить", callback_data="clear"))
    b.row(InlineKeyboardButton(text="⬅️ Меню", callback_data="menu"))
    return b.as_markup()


async def show_cart(c: CallbackQuery, state: FSMContext, menu: Menu):
    cart = await get_cart(state, menu)
    await show(c, cart_text(cart, menu), cart_kb(cart, menu))


# ---------- меню ----------
@router.message(Command("id"))
async def my_id(m: Message):
    await m.answer(f"Ваш Telegram ID: <code>{m.from_user.id}</code>")


@router.message(CommandStart())
@router.message(Command("menu"))
async def start(m: Message, state: FSMContext, menu: Menu):
    await state.set_state(None)
    await m.answer("Добро пожаловать! Выберите категорию:", reply_markup=main_kb(await get_cart(state, menu), menu))


@router.callback_query(F.data == "menu")
async def to_menu(c: CallbackQuery, state: FSMContext, menu: Menu):
    await show(c, "Выберите категорию:", main_kb(await get_cart(state, menu), menu))
    await c.answer()


@router.callback_query(F.data.startswith("cat:"))
async def open_cat(c: CallbackQuery, state: FSMContext, menu: Menu):
    cat = menu.category(c.data.split(":")[1])
    if not cat:
        return await c.answer("Категория не найдена", show_alert=True)
    await show(c, cat.title, cat_kb(cat.id, await get_cart(state, menu), menu))
    await c.answer()


@router.callback_query(F.data.startswith("item:"))
async def open_item(c: CallbackQuery, state: FSMContext, menu: Menu):
    iid = int(c.data.split(":")[1])
    it = menu.item(iid)
    if not it or not it.available:
        return await c.answer("Позиция недоступна", show_alert=True)
    text, kb, photo = item_card(iid, await get_cart(state, menu), menu)
    await show(c, text, kb, photo)
    await c.answer()


@router.callback_query(F.data.startswith("add:"))
async def add_item(c: CallbackQuery, state: FSMContext, menu: Menu):
    iid = int(c.data.split(":")[1])
    it = menu.item(iid)
    if not it or not it.available:
        return await c.answer("Позиция недоступна", show_alert=True)
    cart = await get_cart(state, menu)
    cart[str(iid)] = cart.get(str(iid), 0) + 1
    await state.update_data(cart=cart)
    await c.message.edit_reply_markup(reply_markup=item_card(iid, cart, menu)[1])
    await c.answer(f"Добавлено: {it.name}")


# ---------- корзина ----------
@router.callback_query(F.data == "cart")
async def open_cart(c: CallbackQuery, state: FSMContext, menu: Menu):
    await show_cart(c, state, menu)
    await c.answer()


@router.callback_query(F.data.startswith("add_c:"))
async def cart_add(c: CallbackQuery, state: FSMContext, menu: Menu):
    iid = c.data.split(":")[1]
    cart = await get_cart(state, menu)
    if iid in cart:
        cart[iid] += 1
        await state.update_data(cart=cart)
    await show_cart(c, state, menu)
    await c.answer()


@router.callback_query(F.data.startswith("dec:"))
async def cart_dec(c: CallbackQuery, state: FSMContext, menu: Menu):
    iid = c.data.split(":")[1]
    cart = await get_cart(state, menu)
    if cart.get(iid, 0) > 1:
        cart[iid] -= 1
    else:
        cart.pop(iid, None)
    await state.update_data(cart=cart)
    await show_cart(c, state, menu)
    await c.answer()


@router.callback_query(F.data == "clear")
async def clear(c: CallbackQuery, state: FSMContext, menu: Menu):
    await state.update_data(cart={})
    await show_cart(c, state, menu)
    await c.answer("Корзина очищена")


@router.callback_query(F.data == "noop")
async def noop(c: CallbackQuery):
    await c.answer()


# ---------- оформление ----------
@router.callback_query(F.data == "checkout")
async def checkout(c: CallbackQuery, state: FSMContext, menu: Menu):
    if not await get_cart(state, menu):
        return await c.answer("Корзина пуста", show_alert=True)
    await state.set_state(Checkout.place)
    await c.message.answer("Напишите номер стола (например: <b>5</b>) или слово <b>с собой</b>:")
    await c.answer()


@router.message(Checkout.place, F.text)
async def got_place(m: Message, state: FSMContext):
    t = m.text.strip()
    place = f"Стол {t}" if t.isdigit() else t[:50]
    await state.update_data(place=place)
    await state.set_state(Checkout.comment)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Без комментария", callback_data="nocomment")]])
    await m.answer("Комментарий к заказу (без сахара, овсяное молоко…)?", reply_markup=kb)


async def finish(user_msg: Message, user, state: FSMContext, comment: str, storage: Storage, sinks: list[OrderSink], menu: Menu):
    cart = await get_cart(state, menu)
    if not cart:
        return await user_msg.answer("Корзина пуста. /menu")
    items = [(menu.item(int(i)), q) for i, q in cart.items()]
    lines = [(it.name, q, it.price, it.station) for it, q in items]
    customer = user.full_name + (f" (@{user.username})" if user.username else "")
    place = (await state.get_data())["place"]
    order = await storage.create_order(user.id, customer, place, comment, lines)
    for sink in sinks:
        await sink.send(order)
    await state.clear()
    await user_msg.answer(
        f"✅ Заказ <b>№{order.id}</b> принят!\n{order.total} {CURRENCY}. Мы сообщим, когда он будет готов.\n\n/menu — новый заказ"
    )


@router.message(Checkout.comment, F.text)
async def got_comment(m: Message, state: FSMContext, storage: Storage, sinks: list[OrderSink], menu: Menu):
    await finish(m, m.from_user, state, m.text.strip()[:200], storage, sinks, menu)


@router.callback_query(Checkout.comment, F.data == "nocomment")
async def no_comment(c: CallbackQuery, state: FSMContext, storage: Storage, sinks: list[OrderSink], menu: Menu):
    await c.answer()
    await finish(c.message, c.from_user, state, "", storage, sinks, menu)


# ---------- кнопки персонала ----------
STATUS_TEXT = {
    "accepted": ("👨‍🍳 Принят", "Ваш заказ №{id} принят в работу"),
    "ready": ("✅ Готов", "Ваш заказ №{id} готов! Заберите на выдаче 🎉"),
}


@router.callback_query(F.data.startswith("st:"))
async def staff_status(c: CallbackQuery, storage: Storage):
    _, oid, status = c.data.split(":")
    oid = int(oid)
    label, notify = STATUS_TEXT[status]
    await storage.set_status(oid, status)
    base = c.message.html_text.split("\n\n<i>")[0]
    kb = c.message.reply_markup if status == "accepted" else None
    await c.message.edit_text(f"{base}\n\n<i>{label} — {c.from_user.full_name}</i>", reply_markup=kb)
    uid = await storage.get_user_id(oid)
    if uid:
        try:
            await c.bot.send_message(uid, notify.format(id=oid))
        except Exception:
            pass
    await c.answer(label)
