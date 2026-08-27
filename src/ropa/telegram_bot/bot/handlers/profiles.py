import asyncio
from contextlib import suppress
from html import escape
from pathlib import Path
from typing import Any
from uuid import uuid4

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, Update
from telegram.ext import ContextTypes

from ropa.db import get_mongo_connector
from ropa.profiles import BodyProfile, Measurement

from .utils import keep_uploading_photo

PROFILE_COLLECTION = "profiles"
PROFILE_CALLBACK_PREFIX = "profile:"
BODY_RECONSTRUCTIONS_DIR = Path("resources/generated/body-reconstructions")


def format_profile_option(profile: dict[str, Any]) -> str:
    height = Measurement.model_validate(profile["height"])

    return (
        f"{profile['_id']} // {str(profile['gender']).upper()} // "
        f"{height.value:g} {height.unit.upper()}"
    )


def format_measurement(measurement: Measurement | None) -> str:
    if measurement is None:
        return "—"

    return f"{measurement.value:g} {measurement.unit}"


def format_profile_details(
    profile_id: str,
    gender: str,
    profile: BodyProfile,
) -> str:
    rows = (
        ("Profile", profile_id),
        ("Gender", gender),
        ("Height", format_measurement(profile.height)),
        ("Chest circumference", format_measurement(profile.chest_circumference)),
        ("Waist circumference", format_measurement(profile.waist_circumference)),
        ("Hip circumference", format_measurement(profile.hip_circumference)),
        ("Shoulder width", format_measurement(profile.shoulder_width)),
        ("Arm sleeve length", format_measurement(profile.arm_sleeve_length)),
        ("Inseam length", format_measurement(profile.inseam_length)),
        ("Foot length", format_measurement(profile.foot_length)),
        ("Neck circumference", format_measurement(profile.neck_circumference)),
    )
    label_width = max(len(label) for label, _ in rows) + 1
    details = "\n".join(
        f"{label + ':':<{label_width}}  {value}" for label, value in rows
    )

    return f"<pre>{escape(details)}</pre>"


def get_reconstruction_images(profile_id: str) -> tuple[Path, ...]:
    reconstruction_directory = BODY_RECONSTRUCTIONS_DIR / profile_id
    if not reconstruction_directory.is_dir():
        return ()

    return tuple(
        path
        for path in sorted(reconstruction_directory.iterdir())
        if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
    )


async def show_profiles(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    message = update.message
    if message is None:
        return

    profiles = await get_mongo_connector().find_multiple(
        PROFILE_COLLECTION,
        projection={"_id": True, "gender": True, "height": True},
    ).to_list()
    if not profiles:
        await message.reply_text("No profiles are available.")

        return

    ordered_profiles = sorted(
        profiles,
        key=lambda profile: int(str(profile["_id"]).rsplit("-", maxsplit=1)[-1]),
    )

    keyboard = [
        [
            InlineKeyboardButton(
                format_profile_option(profile),
                callback_data=f"{PROFILE_CALLBACK_PREFIX}{profile['_id']}",
            )
        ]
        for profile in ordered_profiles
    ]
    await message.reply_text(
        "Select a profile:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def select_profile(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    query = update.callback_query
    chat = update.effective_chat
    if query is None or query.data is None or chat is None:
        return

    await query.answer()
    profile_id = query.data.removeprefix(PROFILE_CALLBACK_PREFIX)
    document = await get_mongo_connector().find(
        PROFILE_COLLECTION,
        {"_id": profile_id},
    )
    if document is None:
        await query.edit_message_text("The selected profile is no longer available.")

        return

    chat_data = context.chat_data
    assert chat_data is not None
    profile = BodyProfile.model_validate(document)
    chat_data["profile"] = profile
    chat_data["session_id"] = str(uuid4())

    reconstruction_images = get_reconstruction_images(profile_id)
    if reconstruction_images:
        upload_task = asyncio.create_task(keep_uploading_photo(chat.id, context))
        try:
            await context.bot.send_media_group(
                chat_id=chat.id,
                media=tuple(
                    InputMediaPhoto(image_path.read_bytes(), filename=image_path.name)
                    for image_path in reconstruction_images
                ),
            )
        finally:
            upload_task.cancel()
            with suppress(asyncio.CancelledError):
                await upload_task

    await context.bot.send_message(
        chat_id=chat.id,
        text=format_profile_details(
            profile_id,
            str(document["gender"]),
            profile,
        ),
        parse_mode="HTML",
    )
