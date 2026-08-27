from telegram import Update
from telegram.ext import ContextTypes


async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if update.message is None:
        return

    await update.message.reply_text(
        "Use /profile to select a body profile, then send any garment question."
    )
