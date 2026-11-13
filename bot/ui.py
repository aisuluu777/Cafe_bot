from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message


async def show(c: CallbackQuery, text: str, kb: InlineKeyboardMarkup, photo: str | None = None) -> None:
    """Заменяет текущее сообщение; умеет переходить между текстовым и фото-сообщением."""
    msg = c.message
    if photo:
        await msg.delete()
        await msg.answer_photo(photo, caption=text, reply_markup=kb)
    elif msg.photo:
        await msg.delete()
        await msg.answer(text, reply_markup=kb)
    else:
        await msg.edit_text(text, reply_markup=kb)


async def send(m: Message, text: str, kb: InlineKeyboardMarkup, photo: str | None = None) -> None:
    if photo:
        await m.answer_photo(photo, caption=text, reply_markup=kb)
    else:
        await m.answer(text, reply_markup=kb)
