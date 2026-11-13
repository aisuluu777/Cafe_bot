"""Скрытая админ-панель: /admin (не в списке команд, для остальных молчит). Редактирование меню и фото."""
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton as Btn, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from .config import Config
from .menu import CURRENCY, STATIONS, Menu
from .ui import send, show


async def is_admin(event: Message | CallbackQuery, cfg: Config) -> bool:
    return event.from_user.id in cfg.admin_ids


router = Router()
router.message.filter(is_admin)
router.callback_query.filter(is_admin)

TEXT = F.text & ~F.text.startswith("/")


class Edit(StatesGroup):
    value = State()


class New(StatesGroup):
    name = State()
    price = State()
    station = State()
    photo = State()


# ---------- рендер ----------
def home(menu: Menu):
    b = InlineKeyboardBuilder()
    for c in menu.categories():
        b.button(text=c.title, callback_data=f"adm:c:{c.id}")
    b.adjust(2)
    return "🔧 <b>Редактор меню</b>\nВыберите категорию:", b.as_markup(), None


def category(cat_id: str, menu: Menu):
    cat = menu.category(cat_id)
    b = InlineKeyboardBuilder()
    for it in menu.items(cat_id):
        b.button(text=f"{'' if it.available else '🚫 '}{'📷 ' if it.photo else ''}{it.name} — {it.price} {CURRENCY}",
                 callback_data=f"adm:i:{it.id}")
    b.adjust(1)
    b.row(Btn(text="➕ Добавить блюдо", callback_data=f"adm:new:{cat_id}"))
    b.row(Btn(text="⬅️ Назад", callback_data="adm:home"))
    return f"🔧 {cat.title}", b.as_markup(), None


def item_view(item_id: int, menu: Menu):
    it = menu.item(item_id)
    text = (f"<b>{it.name}</b>\nЦена: {it.price} {CURRENCY}\nСтанция: {STATIONS[it.station]}\n"
            f"Статус: {'в наличии' if it.available else '🚫 в стоп-листе'}\nФото: {'есть' if it.photo else 'нет'}")
    b = InlineKeyboardBuilder()
    b.row(Btn(text="✏️ Название", callback_data=f"adm:f:name:{item_id}"),
          Btn(text="💰 Цена", callback_data=f"adm:f:price:{item_id}"))
    b.row(Btn(text="🖼 Фото", callback_data=f"adm:f:photo:{item_id}"),
          Btn(text="🔄 Бар/Кухня", callback_data=f"adm:st:{item_id}"))
    b.row(Btn(text="✅ Вернуть в меню" if not it.available else "🚫 В стоп-лист", callback_data=f"adm:av:{item_id}"))
    b.row(Btn(text="🗑 Удалить", callback_data=f"adm:del:{item_id}"))
    b.row(Btn(text="⬅️ Назад", callback_data=f"adm:c:{it.cat_id}"))
    return text, b.as_markup(), it.photo


# ---------- навигация ----------
@router.message(Command("admin"))
async def admin_cmd(m: Message, state: FSMContext, menu: Menu):
    await state.clear()
    await send(m, *home(menu))


@router.message(Command("cancel"))
async def cancel(m: Message, state: FSMContext, menu: Menu):
    await state.clear()
    await send(m, *home(menu))


@router.callback_query(F.data == "adm:home")
async def adm_home(c: CallbackQuery, menu: Menu):
    await show(c, *home(menu))
    await c.answer()


@router.callback_query(F.data.startswith("adm:c:"))
async def adm_cat(c: CallbackQuery, menu: Menu):
    await show(c, *category(c.data.split(":")[2], menu))
    await c.answer()


@router.callback_query(F.data.startswith("adm:i:"))
async def adm_item(c: CallbackQuery, menu: Menu):
    await show(c, *item_view(int(c.data.split(":")[2]), menu))
    await c.answer()


# ---------- быстрые действия ----------
@router.callback_query(F.data.startswith("adm:st:"))
async def toggle_station(c: CallbackQuery, menu: Menu):
    iid = int(c.data.split(":")[2])
    it = menu.item(iid)
    menu.update_item(iid, "station", "kitchen" if it.station == "bar" else "bar")
    await show(c, *item_view(iid, menu))
    await c.answer()


@router.callback_query(F.data.startswith("adm:av:"))
async def toggle_available(c: CallbackQuery, menu: Menu):
    iid = int(c.data.split(":")[2])
    menu.update_item(iid, "available", int(not menu.item(iid).available))
    await show(c, *item_view(iid, menu))
    await c.answer()


@router.callback_query(F.data.startswith("adm:del:"))
async def delete_ask(c: CallbackQuery, menu: Menu):
    iid = int(c.data.split(":")[2])
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        Btn(text="🗑 Да, удалить", callback_data=f"adm:delok:{iid}"),
        Btn(text="Отмена", callback_data=f"adm:i:{iid}"),
    ]])
    await show(c, f"Удалить «{menu.item(iid).name}»?", kb)
    await c.answer()


@router.callback_query(F.data.startswith("adm:delok:"))
async def delete_ok(c: CallbackQuery, menu: Menu):
    iid = int(c.data.split(":")[2])
    cat_id = menu.item(iid).cat_id
    menu.delete_item(iid)
    await show(c, *category(cat_id, menu))
    await c.answer("Удалено")


# ---------- редактирование поля ----------
PROMPTS = {"name": "Новое название:", "price": f"Новая цена ({CURRENCY}), числом:", "photo": "Пришлите фото блюда:"}


@router.callback_query(F.data.startswith("adm:f:"))
async def edit_start(c: CallbackQuery, state: FSMContext):
    _, _, field, iid = c.data.split(":")
    await state.set_state(Edit.value)
    await state.update_data(item_id=int(iid), field=field)
    await c.message.answer(PROMPTS[field] + "\n/cancel — отмена")
    await c.answer()


@router.message(Edit.value, F.photo)
@router.message(Edit.value, TEXT)
async def edit_value(m: Message, state: FSMContext, menu: Menu):
    d = await state.get_data()
    field, iid = d["field"], d["item_id"]
    if field == "photo":
        if not m.photo:
            return await m.answer("Нужно фото 📷")
        value = m.photo[-1].file_id
    elif m.photo:
        return await m.answer("Нужен текст")
    elif field == "price":
        if not m.text.strip().isdigit() or int(m.text) <= 0:
            return await m.answer("Цена — целое число больше нуля")
        value = int(m.text)
    else:
        value = m.text.strip()[:60]
    menu.update_item(iid, field, value)
    await state.clear()
    await send(m, *item_view(iid, menu))


# ---------- новое блюдо ----------
@router.callback_query(F.data.startswith("adm:new:"))
async def new_start(c: CallbackQuery, state: FSMContext):
    await state.set_state(New.name)
    await state.update_data(cat_id=c.data.split(":")[2])
    await c.message.answer("Название нового блюда:\n/cancel — отмена")
    await c.answer()


@router.message(New.name, TEXT)
async def new_name(m: Message, state: FSMContext):
    await state.update_data(name=m.text.strip()[:60])
    await state.set_state(New.price)
    await m.answer(f"Цена ({CURRENCY}), числом:")


@router.message(New.price, TEXT)
async def new_price(m: Message, state: FSMContext):
    if not m.text.strip().isdigit() or int(m.text) <= 0:
        return await m.answer("Цена — целое число больше нуля")
    await state.update_data(price=int(m.text))
    await state.set_state(New.station)
    kb = InlineKeyboardMarkup(inline_keyboard=[[Btn(text=t, callback_data=f"adm:ns:{k}") for k, t in STATIONS.items()]])
    await m.answer("Кто готовит?", reply_markup=kb)


@router.callback_query(New.station, F.data.startswith("adm:ns:"))
async def new_station(c: CallbackQuery, state: FSMContext):
    await state.update_data(station=c.data.split(":")[2])
    await state.set_state(New.photo)
    kb = InlineKeyboardMarkup(inline_keyboard=[[Btn(text="Пропустить", callback_data="adm:nskip")]])
    await c.message.answer("Пришлите фото блюда или пропустите:", reply_markup=kb)
    await c.answer()


async def _create(m: Message, state: FSMContext, menu: Menu, photo: str | None):
    d = await state.get_data()
    iid = menu.add_item(d["cat_id"], d["name"], d["price"], d["station"], photo)
    await state.clear()
    await send(m, *item_view(iid, menu))


@router.message(New.photo, F.photo)
async def new_photo(m: Message, state: FSMContext, menu: Menu):
    await _create(m, state, menu, m.photo[-1].file_id)


@router.callback_query(New.photo, F.data == "adm:nskip")
async def new_skip(c: CallbackQuery, state: FSMContext, menu: Menu):
    await c.answer()
    await _create(c.message, state, menu, None)


@router.message(New.photo, TEXT)
async def new_photo_text(m: Message):
    await m.answer("Пришлите фото или нажмите «Пропустить»")
