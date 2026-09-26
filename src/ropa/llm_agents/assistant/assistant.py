from asyncio import Lock
from pathlib import Path

from pydantic import BaseModel, Field
from pydantic_ai import Agent, ModelRetry, RunContext
from pydantic_ai.capabilities import ProcessEventStream, ReinjectSystemPrompt
from pydantic_ai.messages import ModelMessage
from pydantic_ai.models.openai import OpenAIChatModelSettings
from pydantic_ai_harness import SubAgent, SubAgents

from ropa.llm_agents.agent_deps import AssistantDeps
from ropa.llm_agents.history import MAX_HISTORY_MESSAGES, trim_history
from ropa.llm_agents.retrieval_storage import read_retrieved_items_tool
from ropa.llm_agents.retriever import get_retriever
from ropa.llm_agents.utils import tool_logging_handler
from ropa.recommendations import RecommendedItem


class AssistantOutput(BaseModel):
    recommendations: list[RecommendedItem] = Field(
        description="Catalog recommendations ordered from most relevant to least relevant.",
    )


def get_assistant() -> Agent[AssistantDeps, AssistantOutput]:
    agent = Agent(
        name="assistant",
        model="openai-chat:gpt-5.6-sol",
        model_settings=OpenAIChatModelSettings(openai_reasoning_effort="none"),
        deps_type=AssistantDeps,
        output_type=AssistantOutput,
        retries=3,
        tools=[read_retrieved_items_tool],
        capabilities=[
            SubAgents(
                agents=[
                    SubAgent(
                        get_retriever(),
                        max_calls=3,
                        timeout_seconds=120,
                    ),
                ],
                agent_folders=None,
                forward_usage=False,
                contain_errors=True,
            ),
            ProcessEventStream(tool_logging_handler),
            ReinjectSystemPrompt(replace_existing=True),
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

    @agent.output_validator
    def validate_recommendations(
        ctx: RunContext[AssistantDeps],
        output: AssistantOutput,
    ) -> AssistantOutput:
        if any(
            item.gender not in {ctx.deps.profile_gender, "unisex"}
            for item in output.recommendations
        ):
            raise ModelRetry(
                "Return only recommendations matching the profile gender or unisex items."
            )

        return output

    return agent


class Assistant:
    def __init__(self, max_history_messages: int = MAX_HISTORY_MESSAGES):
        if max_history_messages < 1:
            raise ValueError("max_history_messages must be positive")

        self.agent = get_assistant()
        self.max_history_messages = max_history_messages
        self.message_history: list[ModelMessage] = []
        self.lock = Lock()

    async def generate(
        self,
        user_prompt: str,
        agent_deps: AssistantDeps,
    ) -> AssistantOutput:
        async with self.lock:
            result = await self.agent.run(
                user_prompt,
                deps=agent_deps,
                message_history=self.message_history,
            )

            self.message_history = trim_history(
                result.all_messages(),
                self.max_history_messages,
            )

            return result.output
