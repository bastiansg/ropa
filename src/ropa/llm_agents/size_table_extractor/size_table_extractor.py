from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from pydantic_ai import Agent, PromptedOutput
from pydantic_ai.models.openai import OpenAIChatModelSettings


class SizeTableExtractorOutput(BaseModel):
    data: list[dict[str, Any]] | dict[str, Any] = Field(
        description="Extracted JSON content without presentational wrappers.",
    )


def get_size_table_extractor() -> Agent[None, SizeTableExtractorOutput]:
    agent = Agent(
        name="size-table-extractor",
        model="openai-chat:gpt-5.6-sol",
        model_settings=OpenAIChatModelSettings(openai_reasoning_effort="none"),
        output_type=PromptedOutput(SizeTableExtractorOutput),
        retries=3,
        max_concurrency=10,
        defer_model_check=True,
    )

    @agent.system_prompt
    async def get_system_prompt() -> str:
        return Path(__file__).with_name("system-prompt.md").read_text()

    return agent
