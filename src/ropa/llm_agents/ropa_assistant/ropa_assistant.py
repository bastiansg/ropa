from pathlib import Path

from llm_agents.message_history import MongoDBMessageHistory
from llm_agents.meta.interfaces import LLMAgent
from pydantic import BaseModel, Field, StrictStr
from pydantic_ai import Agent, NativeOutput, RunContext
from pydantic_ai.capabilities import ReinjectSystemPrompt
from pydantic_ai.models.openai import OpenAIChatModelSettings

from ropa.llm_agents.tools import (
    centimeters_to_eu_footwear_size_tool,
    centimeters_to_us_footwear_size_tool,
    get_catalog_schema_tool,
    ontology_tools,
    search_catalog_tool,
)
from ropa.llm_agents.utils import hide_tools_after_limit, tool_logging_handler
from ropa.profiles import BodyProfile


class RopaAssistantInput(BaseModel):
    question: StrictStr
    profile: BodyProfile


class RopaAssistantOutput(BaseModel):
    recommended_item_ids: list[StrictStr] = Field(
        description=(
            "MongoDB `_id` values of the documents, ordered from most to least "
            "relevant."
        ),
    )


agent = Agent(
    name="ropa-assistant",
    model="gpt-5.6-sol",
    model_settings=OpenAIChatModelSettings(openai_reasoning_effort="none"),
    system_prompt=LLMAgent.read_file(
        file_path=str(Path(__file__).with_name("system-prompt.md"))
    ),
    deps_type=RopaAssistantInput,
    output_type=NativeOutput(RopaAssistantOutput),
    retries=3,
    tools=[
        get_catalog_schema_tool,
        search_catalog_tool,
        *ontology_tools,
        centimeters_to_eu_footwear_size_tool,
        centimeters_to_us_footwear_size_tool,
    ],
    prepare_tools=hide_tools_after_limit,  # type: ignore
    event_stream_handler=tool_logging_handler,  # type: ignore
    capabilities=[ReinjectSystemPrompt()],
)


@agent.system_prompt
async def get_system_prompt(ctx: RunContext[RopaAssistantInput]) -> str:
    system_prompt = LLMAgent.read_file(
        file_path=str(Path(__file__).with_name("system-prompt.md"))
    )

    return system_prompt.format(**ctx.deps.model_dump())


class RopaAssistant(LLMAgent[RopaAssistantInput, RopaAssistantOutput]):
    def __init__(
        self,
        max_concurrency: int = 10,
        mongodb_message_history: MongoDBMessageHistory | None = None,
    ):
        super().__init__(
            agent=agent,
            max_concurrency=max_concurrency,
            mongodb_message_history=mongodb_message_history,
        )
