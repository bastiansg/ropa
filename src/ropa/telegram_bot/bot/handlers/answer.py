import asyncio
from contextlib import suppress
from html import escape
from typing import Any

from llm_agents.message_history import MongoDBMessageHistory
from telegram import Update
from telegram.ext import ContextTypes

from ropa.config import config
from ropa.db import get_mongo_connector
from ropa.llm_agents import RopaAssistant, RopaAssistantInput
from ropa.profiles import BodyProfile

from .utils import keep_typing

CATALOG_COLLECTION = "catalog_items"


def format_product(index: int, product: dict[str, Any]) -> str:
    return "\n".join(
        (
            f"<b>{index}. {escape(str(product['title']))}</b>",
            "",
            escape(str(product["description"])),
            "",
            f"<b>Price:</b> {product['price']}",
            f"<b>Provider:</b> {escape(str(product['vendor']))}",
            f'<b>URL:</b> <a href="{escape(str(product["url"]), quote=True)}">'
            "View product</a>",
        )
    )


async def get_recommended_products(
    recommended_item_ids: list[str],
) -> list[dict[str, Any]]:
    products = (
        await get_mongo_connector()
        .find_multiple(
            CATALOG_COLLECTION,
            {"_id": {"$in": recommended_item_ids}},
            projection={
                "title": True,
                "description": True,
                "price": True,
                "vendor": True,
                "url": True,
            },
        )
        .to_list()
    )
    products_by_id = {str(product["_id"]): product for product in products}

    return [
        products_by_id[item_id]
        for item_id in recommended_item_ids
        if item_id in products_by_id
    ]


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
    session_id = chat_data.get("session_id") if chat_data is not None else None
    if not isinstance(profile, BodyProfile) or not isinstance(session_id, str):
        await message.reply_text("Select a body profile first with /profile.")

        return

    assistant = RopaAssistant(
        mongodb_message_history=MongoDBMessageHistory(
            session_id=session_id,
            mongodb_dsn=config.mongodb_dsn,
            mongodb_db_name=config.mongodb_db_name,
            # save_tool_messages=True,
        ),
    )
    typing_task = asyncio.create_task(keep_typing(chat.id, context))
    try:
        async with assistant.agent:
            result = await assistant.generate(
                user_prompt=message.text,
                agent_deps=RopaAssistantInput(
                    question=message.text,
                    profile=profile,
                ),
            )
    finally:
        typing_task.cancel()
        with suppress(asyncio.CancelledError):
            await typing_task

    products = await get_recommended_products(result.recommended_item_ids)
    if not products:
        await message.reply_text("No suitable products were found.")

        return

    for index, product in enumerate(products, start=1):
        await message.reply_text(
            format_product(index, product),
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
