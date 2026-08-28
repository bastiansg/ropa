from pathlib import Path

from llm_agents.meta.interfaces import LLMAgent
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


agent = Agent(
    name="garment-color-extractor",
    model="openai-chat:gpt-5.6-sol",
    model_settings=OpenAIChatModelSettings(openai_reasoning_effort="none"),
    system_prompt=LLMAgent.read_file(
        file_path=str(Path(__file__).with_name("system-prompt.md"))
    ),
    deps_type=GarmentColorExtractorInput,
    output_type=PromptedOutput(GarmentColorExtractorOutput),
    retries=3,
    defer_model_check=True,
)


@agent.system_prompt
async def get_system_prompt(ctx: RunContext[GarmentColorExtractorInput]) -> str:
    system_prompt = LLMAgent.read_file(
        file_path=str(Path(__file__).with_name("system-prompt.md"))
    )

    return system_prompt.format(**ctx.deps.model_dump())


class GarmentColorExtractor(
    LLMAgent[GarmentColorExtractorInput, GarmentColorExtractorOutput]
):
    def __init__(self, max_concurrency: int = 10):
        super().__init__(agent=agent, max_concurrency=max_concurrency)
