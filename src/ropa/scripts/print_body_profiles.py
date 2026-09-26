from itertools import islice

from rich.console import Console
from rich.table import Table

from ropa.loaders import BodyMLoader
from ropa.meta.interfaces import Measurement
from ropa.scripts.console import cyberpunk_table

PROFILE_LIMIT = 10


def format_measurement(measurement: Measurement | None) -> str:
    if measurement is None:
        return "—"

    return f"{measurement.value:g} {measurement.unit}"


def profiles_table() -> Table:
    table = cyberpunk_table(f":: BODY PROFILES // FIRST {PROFILE_LIMIT} ::")
    columns = (
        ("SUBJECT", "bright_cyan"),
        ("PHOTO", "dim white"),
        ("GENDER", "bright_magenta"),
        ("HEIGHT", "white"),
        ("CHEST", "white"),
        ("WAIST", "white"),
        ("HIP", "white"),
        ("SHOULDER", "white"),
        ("SLEEVE", "white"),
        ("LEG", "white"),
    )
    for heading, style in columns:
        table.add_column(heading, style=style, no_wrap=True)

    for profile in islice(BodyMLoader().load(), PROFILE_LIMIT):
        table.add_row(
            profile.subject_id,
            profile.photo_id,
            profile.gender,
            format_measurement(profile.height),
            format_measurement(profile.chest_circumference),
            format_measurement(profile.waist_circumference),
            format_measurement(profile.hip_circumference),
            format_measurement(profile.shoulder_width),
            format_measurement(profile.arm_sleeve_length),
            format_measurement(profile.leg_length),
        )

    return table


def main() -> None:
    Console().print(profiles_table())


if __name__ == "__main__":
    main()
