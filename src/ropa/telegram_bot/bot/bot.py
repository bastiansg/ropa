import os

import logfire
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from ropa.config import config

from .console import render_header, render_listening_status
from .handlers import answer, select_profile, show_profiles, start
from .handlers.profiles import PROFILE_CALLBACK_PREFIX

if os.getenv("LOGFIRE_TOKEN") is not None:
    logfire.configure(service_name="dev")
    logfire.instrument_pydantic_ai()
    logfire.instrument_openai()


app = ApplicationBuilder().token(config.telegram_bot_token).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("profile", show_profiles))
app.add_handler(
    CallbackQueryHandler(
        select_profile,
        pattern=f"^{PROFILE_CALLBACK_PREFIX}",
    )
)
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, answer))

render_header()
render_listening_status()
app.run_polling()
