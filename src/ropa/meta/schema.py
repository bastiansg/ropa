from typing import Literal

from pydantic import BaseModel, Field, PositiveInt


class BodyMeasurements(BaseModel):
    size_label: Literal["XS", "S", "M", "L", "XL", "XXL"] = Field(
        description="Clothing size label associated with the measurements.",
    )

    chest_circumference: PositiveInt = Field(
        description="Chest circumference in centimeters.",
    )

    waist_circumference: PositiveInt = Field(
        description="Waist circumference in centimeters.",
    )

    hip_circumference: PositiveInt = Field(
        description="Hip circumference in centimeters.",
    )

    jeans_size: PositiveInt | None = Field(
        default=None,
        description="Equivalent numeric jeans size when provided.",
    )
