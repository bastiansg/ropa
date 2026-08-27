from html import escape
from typing import Any
from uuid import uuid4

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from ropa.db import get_mongo_connector
from ropa.profiles import BodyProfile, Measurement

PROFILE_COLLECTION = "profiles"
PROFILE_CALLBACK_PREFIX = "profile:"


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
    label_width = max(len(label) for label, _ in rows)
    details = "\n".join(
        f"{label.upper():<{label_width}}  {value}" for label, value in rows
    )

    return f"Profile selected:\n\n<pre>{escape(details)}</pre>"


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

    keyboard = [
        [
            InlineKeyboardButton(
                format_profile_option(profile),
                callback_data=f"{PROFILE_CALLBACK_PREFIX}{profile['_id']}",
            )
        ]
        for profile in profiles
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
    if query is None or query.data is None:
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

    await query.edit_message_text(
        format_profile_details(
            profile_id,
            str(document["gender"]),
            profile,
        ),
        parse_mode="HTML",
    )
