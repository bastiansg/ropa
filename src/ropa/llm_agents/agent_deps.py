from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, StrictStr

from ropa.meta.interfaces import BodyProfile


class AssistantDeps(BaseModel):
    catalog_schema: dict[str, Any]
    profile: BodyProfile
    profile_gender: StrictStr
    profile_id: StrictStr
    request_id: str = Field(default_factory=lambda: str(uuid4()))
    retrieved_items: dict[str, dict[str, Any]] = Field(default_factory=dict, exclude=True)
    retrieval_keys: set[str] = Field(default_factory=set, exclude=True)
