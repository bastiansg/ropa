from pathlib import Path

from pydantic import BaseModel, Field, StrictStr
from pydantic_ai import Agent, PromptedOutput, RunContext
from pydantic_ai.models.openai import OpenAIChatModelSettings


class GarmentColorExtractorInput(BaseModel):
    title: StrictStr
    description: StrictStr


class GarmentColorExtractorOutput(BaseModel):
    color: str = Field(
        description="Color of the garment identified by the title and description.",
    )


def get_garment_color_extractor() -> Agent[
    GarmentColorExtractorInput, GarmentColorExtractorOutput
]:
    agent = Agent(
        name="garment-color-extractor",
        model="openai-chat:gpt-5.6-sol",
        model_settings=OpenAIChatModelSettings(openai_reasoning_effort="none"),
        deps_type=GarmentColorExtractorInput,
        output_type=PromptedOutput(GarmentColorExtractorOutput),
        retries=3,
        max_concurrency=10,
        defer_model_check=True,
    )

    @agent.system_prompt
    async def get_system_prompt(ctx: RunContext[GarmentColorExtractorInput]) -> str:
        system_prompt = Path(__file__).with_name("system-prompt.md").read_text()

        return system_prompt.format(**ctx.deps.model_dump())

    return agent
