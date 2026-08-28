from pathlib import Path
from typing import Any

from llm_agents.meta.interfaces import LLMAgent
from pydantic import BaseModel, Field
from pydantic_ai import Agent, PromptedOutput
from pydantic_ai.models.openai import OpenAIChatModelSettings


class SizeTableExtractorOutput(BaseModel):
    data: list[dict[str, Any]] | dict[str, Any] = Field(
        description="Extracted JSON content without presentational wrappers.",
    )


agent = Agent(
    name="size-table-extractor",
    model="openai-chat:gpt-5.6-sol",
    model_settings=OpenAIChatModelSettings(openai_reasoning_effort="none"),
    system_prompt=LLMAgent.read_file(
        file_path=str(Path(__file__).with_name("system-prompt.md"))
    ),
    output_type=PromptedOutput(SizeTableExtractorOutput),
    retries=3,
    defer_model_check=True,
)


@agent.system_prompt
async def get_system_prompt() -> str:
    return LLMAgent.read_file(
        file_path=str(Path(__file__).with_name("system-prompt.md"))
    )


class SizeTableExtractor(LLMAgent[None, SizeTableExtractorOutput]):
    def __init__(self, max_concurrency: int = 10):
        super().__init__(agent=agent, max_concurrency=max_concurrency)
