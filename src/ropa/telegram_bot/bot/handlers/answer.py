import asyncio
from contextlib import suppress
from functools import lru_cache
from html import escape
from uuid import uuid4

from llm_agents.message_history import MongoDBMessageHistory
from telegram import Update
from telegram.ext import ContextTypes

from ropa.config import config
from ropa.llm_agents import RopaAssistant, RopaAssistantDeps
from ropa.llm_agents.tools import get_catalog_schema
from ropa.profiles import BodyProfile
from ropa.recommendations import RecommendedItem, get_recommendations

from .utils import keep_typing


@lru_cache(maxsize=10)
def get_assistant(session_id: str) -> RopaAssistant:
    return RopaAssistant(
        mongodb_message_history=MongoDBMessageHistory(
            session_id=session_id,
            mongodb_dsn=config.mongodb_dsn,
            mongodb_db_name=config.mongodb_db_name,
            # save_tool_messages=True,
        ),
    )


def format_product(
    index: int,
    product: RecommendedItem,
) -> str:
    return "\n".join(
        (
            f"<b>{index}. {escape(product.title)}</b>",
            "",
            escape(product.description),
            "",
            "<b>Matches:</b>",
            *(f"• {escape(match)}" for match in product.matches),
            "",
            f"<b>Price:</b> {product.price}",
            f"<b>Provider:</b> {escape(product.vendor)}",
            (
                f'<b>URL:</b> <a href="{escape(product.url, quote=True)}">'
                "View product</a>"
            ),
        )
    )


async def answer(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    message = update.message
    chat = update.effective_chat
    if message is None or chat is None or message.text is None:
        return

    chat_data = context.chat_data
    profile = chat_data.get("profile") if chat_data is not None else None
    profile_id = chat_data.get("profile_id") if chat_data is not None else None
    session_id = chat_data.get("session_id") if chat_data is not None else None
    if (
        not isinstance(profile, BodyProfile)
        or not isinstance(profile_id, str)
        or not isinstance(session_id, str)
    ):
        await message.reply_text("Select a body profile first with /profile.")

        return

    assistant = get_assistant(session_id=session_id)
    request_id = str(uuid4())
    typing_task = asyncio.create_task(keep_typing(chat.id, context))
    try:
        async with assistant.agent:
            await assistant.generate(
                user_prompt=f"User's request: {message.text}",
                agent_deps=RopaAssistantDeps(
                    catalog_schema=await get_catalog_schema(),
                    profile=profile,
                    profile_id=profile_id,
                    request_id=request_id,
                ),
            )
    finally:
        typing_task.cancel()
        with suppress(asyncio.CancelledError):
            await typing_task

    products = await get_recommendations(request_id)

    if not products:
        await message.reply_text("No suitable products were found.")

        return

    for index, product in enumerate(products, start=1):
        await message.reply_text(
            format_product(index, product),
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
