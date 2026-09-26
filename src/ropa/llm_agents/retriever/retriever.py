from asyncio import Lock
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from pydantic_ai import Agent, AgentRunResult, RunContext, ToolOutput
from pydantic_ai.capabilities import (
    PrepareTools,
    ProcessEventStream,
)
from pydantic_ai.messages import UserContent
from pydantic_ai.models.openai import OpenAIChatModelSettings

from ropa.llm_agents.agent_deps import AssistantDeps
from ropa.llm_agents.retrieval_storage import (
    RetrievalOutput,
    finish_search,
    search_items_tool,
)
from ropa.llm_agents.tools import (
    centimeters_to_eu_footwear_size_tool,
    centimeters_to_us_footwear_size_tool,
    ontology_tools,
)
from ropa.llm_agents.utils import hide_tools_after_limit, tool_logging_handler


class Retriever(Agent[AssistantDeps, RetrievalOutput]):
    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)
        self.lock = Lock()

    async def run(
        self,
        user_prompt: str | Sequence[UserContent] | None = None,
        **kwargs: Any,
    ) -> AgentRunResult[RetrievalOutput]:
        async with self.lock:
            kwargs["deps"].retrieved_items.clear()
            kwargs["message_history"] = None
            return await super().run(user_prompt, **kwargs)


def get_retriever() -> Retriever:
    agent = Retriever(
        name="retriever",
        description="Searches the garment catalog for items matching the request and body profile.",
        model="openai-chat:gpt-5.6-luna",
        model_settings=OpenAIChatModelSettings(openai_reasoning_effort="none"),
        deps_type=AssistantDeps,
        output_type=ToolOutput(finish_search, name="finish_search"),
        retries=3,
        tools=[
            search_items_tool,
            *ontology_tools,
            centimeters_to_eu_footwear_size_tool,
            centimeters_to_us_footwear_size_tool,
        ],
        capabilities=[
            PrepareTools(hide_tools_after_limit),
            ProcessEventStream(tool_logging_handler),
        ],
        defer_model_check=True,
    )

    @agent.system_prompt(dynamic=True)
    def get_system_prompt(ctx: RunContext[AssistantDeps]) -> str:
        return (
            Path(__file__)
            .with_name("system-prompt.md")
            .read_text()
            .format(
                **ctx.deps.model_dump(),
            )
        )

    return agent
