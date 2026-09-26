from html import escape
from uuid import uuid4

from telegram import Update
from telegram.ext import ContextTypes

from ropa.config import config
from ropa.loaders import BodyMLoader, BodyMProfile
from ropa.meta.interfaces import BodyProfile, Measurement

BODYM_LOADER = BodyMLoader()
BODYM_PROFILES = BODYM_LOADER.iter_random_profiles()


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
        ("Leg length", format_measurement(profile.leg_length)),
    )
    label_width = max(len(label) for label, _ in rows) + 1
    details = "\n".join(
        f"{label + ':':<{label_width}}  {value}" for label, value in rows
    )

    return f"<pre>{escape(details)}</pre>"


async def get_profile(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    message = update.message
    if message is None:
        return

    profile = next(BODYM_PROFILES)
    assert isinstance(profile, BodyMProfile)
    chat_data = context.chat_data
    assert chat_data is not None
    chat_data["profile"] = profile
    chat_data["profile_gender"] = config.gender_aliases.get(
        profile.gender,
        profile.gender,
    )
    chat_data["profile_id"] = profile.subject_id
    chat_data["session_id"] = str(uuid4())

    await message.reply_text(
        format_profile_details(
            profile.subject_id,
            profile.gender,
            profile,
        ),
        parse_mode="HTML",
    )
    mask_path = BODYM_LOADER.get_preprocessed_mask_path(profile)
    await message.reply_photo(
        photo=mask_path.read_bytes(),
        filename=mask_path.name,
        read_timeout=config.telegram_media_timeout_seconds,
        write_timeout=config.telegram_media_timeout_seconds,
    )
