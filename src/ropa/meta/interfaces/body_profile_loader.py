from abc import ABC, abstractmethod
from typing import Literal

from pydantic import BaseModel, Field


class Measurement(BaseModel):
    value: float = Field(gt=0)
    unit: Literal["cm"] = "cm"


class BodyProfile(BaseModel):
    height: Measurement
    chest_circumference: Measurement
    waist_circumference: Measurement
    hip_circumference: Measurement
    shoulder_width: Measurement | None
    arm_sleeve_length: Measurement | None
    leg_length: Measurement | None


class BodyProfileLoader(ABC):

    @abstractmethod
    def load(self) -> list[BodyProfile]:
        pass
