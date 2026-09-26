import asyncio
from contextlib import suppress
from functools import lru_cache
from html import escape

from telegram import Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from ropa.llm_agents import Assistant, AssistantDeps
from ropa.llm_agents.tools import get_catalog_schema
from ropa.meta.interfaces import BodyProfile
from ropa.recommendations import RecommendedItem

from .utils import keep_typing


@lru_cache(maxsize=10)
def get_assistant(session_id: str) -> Assistant:
    return Assistant()


def format_product(
    index: int,
    product: RecommendedItem,
) -> str:
    return "\n".join(
        (
            f"<b>{index}. {escape(product.title)} // {escape(product.gender)}</b>",
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
    profile_gender = (
        chat_data.get("profile_gender") if chat_data is not None else None
    )
    profile_id = chat_data.get("profile_id") if chat_data is not None else None
    session_id = chat_data.get("session_id") if chat_data is not None else None
    if (
        not isinstance(profile, BodyProfile)
        or not isinstance(profile_gender, str)
        or not isinstance(profile_id, str)
        or not isinstance(session_id, str)
    ):
        await message.reply_text("Get a body profile first with /get_profile.")

        return

    assistant = get_assistant(session_id=session_id)
    typing_task = asyncio.create_task(keep_typing(chat.id, context))
    try:
        output = await assistant.generate(
            user_prompt=f"User's request: {message.text}",
            agent_deps=AssistantDeps(
                catalog_schema=await get_catalog_schema(),
                profile=profile,
                profile_gender=profile_gender,
                profile_id=profile_id,
            ),
        )
    finally:
        typing_task.cancel()
        with suppress(asyncio.CancelledError):
            await typing_task

    products = output.recommendations

    if not products:
        await message.reply_text("No suitable products were found.")

        return

    for index, product in enumerate(products, start=1):
        product_message = format_product(index, product)
        if product.image_urls:
            try:
                await message.reply_photo(
                    photo=product.image_urls[0],
                    caption=product_message,
                    parse_mode="HTML",
                )

                continue
            except BadRequest as error:
                if "failed to get http url content" not in str(error).lower():
                    raise

        await message.reply_text(
            product_message,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
