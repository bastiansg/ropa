import asyncio

from telegram.constants import ChatAction
from telegram.ext import ContextTypes


async def keep_typing(
    chat_id: int,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    while True:
        await context.bot.send_chat_action(
            chat_id=chat_id,
            action=ChatAction.TYPING,
        )
        await asyncio.sleep(4)


async def keep_uploading_photo(
    chat_id: int,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    while True:
        await context.bot.send_chat_action(
            chat_id=chat_id,
            action=ChatAction.UPLOAD_PHOTO,
        )
        await asyncio.sleep(4)
