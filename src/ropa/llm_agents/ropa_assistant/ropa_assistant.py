from pathlib import Path
from typing import Any

from llm_agents.message_history import MongoDBMessageHistory
from llm_agents.meta.interfaces import LLMAgent
from pydantic import BaseModel, Field, StrictBool, StrictStr
from pydantic_ai import Agent, NativeOutput, RunContext
from pydantic_ai.capabilities import (
    PrepareTools,
    ProcessEventStream,
    ReinjectSystemPrompt,
)
from pydantic_ai.models.openai import OpenAIChatModelSettings

from ropa.llm_agents.tools import (
    centimeters_to_eu_footwear_size_tool,
    centimeters_to_us_footwear_size_tool,
    ontology_tools,
    search_catalog_tool,
    store_recommended_items_tool,
)
from ropa.llm_agents.utils import hide_tools_after_limit, tool_logging_handler
from ropa.profiles import BodyProfile


class RopaAssistantDeps(BaseModel):
    catalog_schema: dict[str, Any]
    profile: BodyProfile
    profile_id: StrictStr
    request_id: StrictStr


class RopaAssistantOutput(BaseModel):
    recommendations_stored: StrictBool = Field(
        description="Whether the recommendations were stored successfully.",
    )


agent = Agent(
    name="ropa-assistant",
    model="openai-chat:gpt-5.6-terra",
    model_settings=OpenAIChatModelSettings(openai_reasoning_effort="none"),
    deps_type=RopaAssistantDeps,
    output_type=NativeOutput(RopaAssistantOutput),
    retries=3,
    tools=[
        search_catalog_tool,
        store_recommended_items_tool,
        *ontology_tools,
        centimeters_to_eu_footwear_size_tool,
        centimeters_to_us_footwear_size_tool,
    ],
    capabilities=[
        PrepareTools(hide_tools_after_limit),  # type: ignore
        ProcessEventStream(tool_logging_handler),  # type: ignore
        ReinjectSystemPrompt(replace_existing=True),
    ],
)


@agent.system_prompt(dynamic=True)
async def get_system_prompt(ctx: RunContext[RopaAssistantDeps]) -> str:
    system_prompt = LLMAgent.read_file(
        file_path=str(Path(__file__).with_name("system-prompt.md"))
    )

    return system_prompt.format(**ctx.deps.model_dump())


class RopaAssistant(LLMAgent[RopaAssistantDeps, RopaAssistantOutput]):
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
