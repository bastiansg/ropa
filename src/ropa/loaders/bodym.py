import csv
import random
from collections.abc import Iterator, Mapping
from itertools import cycle
from pathlib import Path

from pydantic import StrictStr

from ropa.config import config
from ropa.meta.interfaces.body_profile_loader import (
    BodyProfile,
    BodyProfileLoader,
    Measurement,
)


class BodyMProfile(BodyProfile):
    subject_id: StrictStr
    photo_id: StrictStr
    gender: StrictStr


def _measurement(row: Mapping[str, str | None], column: str) -> Measurement:
    value = row[column]
    if value is None:
        raise ValueError(f"Missing BodyM measurement: {column}")

    return Measurement(value=float(value))


def _value(row: Mapping[str, str | None], column: str) -> str:
    value = row[column]
    if value is None:
        raise ValueError(f"Missing BodyM value: {column}")

    return value


def _body_profile_from_row(
    row: Mapping[str, str | None],
    genders: Mapping[str, str],
    photo_ids: Mapping[str, str],
) -> BodyMProfile:
    subject_id = _value(row, "subject_id")

    return BodyMProfile(
        subject_id=subject_id,
        photo_id=photo_ids[subject_id],
        gender=genders[subject_id],
        height=_measurement(row, "height"),
        chest_circumference=_measurement(row, "chest"),
        waist_circumference=_measurement(row, "waist"),
        hip_circumference=_measurement(row, "hip"),
        shoulder_width=_measurement(row, "shoulder-breadth"),
        arm_sleeve_length=_measurement(row, "arm-length"),
        leg_length=_measurement(row, "leg-length"),
    )


class BodyMLoader(BodyProfileLoader):

    def __init__(self, train_directory: Path = config.bodym_train_directory) -> None:
        self.train_directory = train_directory

    def load(self) -> list[BodyProfile]:
        with (self.train_directory / "hwg_metadata.csv").open(
            encoding="utf-8",
            newline="",
        ) as metadata_file:
            genders = {
                _value(row, "subject_id"): _value(row, "gender")
                for row in csv.DictReader(metadata_file)
            }

        with (self.train_directory / "subject_to_photo_map.csv").open(
            encoding="utf-8",
            newline="",
        ) as photo_map_file:
            photo_ids = {
                _value(row, "subject_id"): _value(row, "photo_id")
                for row in csv.DictReader(photo_map_file)
            }

        with (self.train_directory / "measurements.csv").open(
            encoding="utf-8",
            newline="",
        ) as measurements_file:
            return [
                _body_profile_from_row(row, genders, photo_ids)
                for row in csv.DictReader(measurements_file)
            ]

    def iter_random_profiles(self) -> Iterator[BodyProfile]:
        profiles = self.load()
        profiles_by_gender = {
            gender: [profile for profile in profiles if profile.gender == gender]
            for gender in ("female", "male")
        }
        for profiles_for_gender in profiles_by_gender.values():
            random.shuffle(profiles_for_gender)

        genders = random.sample(("female", "male"), k=2)
        for gender in cycle(genders):
            if not profiles_by_gender[gender]:
                profiles_by_gender[gender] = [
                    profile for profile in profiles if profile.gender == gender
                ]
                random.shuffle(profiles_by_gender[gender])

            yield profiles_by_gender[gender].pop()

    def get_mask_paths(self, profile: BodyMProfile) -> tuple[Path, Path]:
        filename = f"{profile.photo_id}.png"

        return (
            self.train_directory / "mask" / filename,
            self.train_directory / "mask_left" / filename,
        )
