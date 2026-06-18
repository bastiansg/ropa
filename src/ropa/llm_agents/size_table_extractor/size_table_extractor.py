from pathlib import Path

from pydantic import BaseModel, Field
from pydantic_ai import Agent, NativeOutput
from pydantic_ai.models.openai import OpenAIChatModelSettings

from llm_agents.meta.interfaces import LLMAgent

from ropa.meta.schema import BodyMeasurements


class SizeTableExtractorOutput(BaseModel):
    body_measurements: list[BodyMeasurements] = Field(
        description=(
            "Body measurements extracted from every visible size-table row."
        ),
    )


agent = Agent(  # type: ignore
    name="size-table-extractor",
    model="openai:gpt-5.4-mini-2026-03-17",
    model_settings=OpenAIChatModelSettings(openai_reasoning_effort="none"),
    system_prompt=LLMAgent.read_file(
        file_path=str(Path(__file__).with_name("system-prompt.md"))
    ),
    output_type=NativeOutput(SizeTableExtractorOutput),
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
