import json
import unittest
from unittest.mock import AsyncMock, patch
from types import SimpleNamespace

from pydantic_ai import RunContext

from pydantic_ai.messages import (
    ModelRequest,
    SystemPromptPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.models.function import DeltaToolCall, FunctionModel

from ropa.llm_agents import (
    GarmentColorExtractorInput,
    Assistant,
    AssistantDeps,
    get_garment_color_extractor,
    get_size_table_extractor,
)
from ropa.llm_agents.retriever import get_retriever
from ropa.meta.interfaces import BodyProfile


def make_deps():
    return AssistantDeps(
        catalog_schema={"title": "Garment title"},
        profile=BodyProfile.model_construct(),
        profile_gender="man",
        profile_id="profile-1",
    )


async def final_response(messages, info):
    yield {0: DeltaToolCall(name="final_result", json_args='{"recommendations": []}')}


class AssistantTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.cached_items = {}

        async def save(key, items, ttl):
            self.cached_items[key] = items

        self.cache_patch = patch(
            "ropa.llm_agents.retrieval_storage.cache",
            SimpleNamespace(set=AsyncMock(side_effect=save), get=AsyncMock(side_effect=self.cached_items.get)),
        )
        self.cache_patch.start()
        self.addCleanup(self.cache_patch.stop)

    async def test_delegation_returns_recommendations_directly(self):
        retriever = get_retriever()
        document = {
            "_id": "item-1", "title": "blue shirt", "gender": "man",
            "vendor": "Test", "product_id": 1, "url": "https://example.com/shirt",
            "description": "Blue shirt", "image_urls": [], "colors": ["blue"],
            "price": 100, "categories": ["camisas"], "all_sizes": ["M"],
            "available_sizes": ["M"], "size_guide_url": None, "size_guide": None,
        }

        mongo_patch = patch("ropa.llm_agents.retrieval_storage.get_mongo_connector")
        connector = mongo_patch.start()
        self.addCleanup(mongo_patch.stop)
        connector.return_value.find_multiple.return_value.to_list = AsyncMock(return_value=[document])

        async def retrieval_response(messages, info):
            self.assertIn("search_catalog", {tool.name for tool in info.function_tools})
            self.assertNotIn("store_recommended_items", {tool.name for tool in info.function_tools})
            prompt = "\n".join(
                part.content
                for message in messages
                for part in message.parts
                if isinstance(part, SystemPromptPart)
            )

            self.assertIn("man", prompt)
            self.assertIn("Garment title", prompt)
            if isinstance(messages[-1].parts[0], ToolReturnPart):
                yield {
                    0: DeltaToolCall(
                        name="finish_search",
                        json_args=json.dumps({"document_ids": ["item-1"]}),
                    ),
                }

                return

            yield {
                0: DeltaToolCall(
                    name="search_catalog",
                    json_args=json.dumps({"filter": {"gender": "man"}, "limit": 5}),
                ),
            }


        async def assistant_response(messages, info):
            self.assertEqual(
                {tool.name for tool in info.function_tools},
                {"delegate_task", "read_retrieved_items"},
            )

            part = messages[-1].parts[0]
            if isinstance(part, ToolReturnPart):
                if part.tool_name == "delegate_task":
                    search_id = next(iter(self.cached_items))
                    self.assertNotIn("blue shirt", str(part.content))
                    yield {0: DeltaToolCall(name="read_retrieved_items", json_args=json.dumps({"search_id": search_id}))}
                    return

                self.assertEqual(part.tool_name, "read_retrieved_items")
                self.assertIn("item-1", str(part.content))
                yield {
                    0: DeltaToolCall(
                        name="final_result",
                        json_args=json.dumps({
                            "recommendations": [{**document, "matches": ["blue"]}],
                        }),
                    ),
                }

                return

            yield {
                0: DeltaToolCall(
                    name="delegate_task",
                    json_args=json.dumps({"agent_name": "retriever", "task": "Find a blue shirt"}),
                ),
            }


        async def search_catalog(ctx: RunContext[AssistantDeps], filter: dict, limit: int = 50):
            self.assertEqual(filter, {"gender": "man"})
            ctx.deps.retrieved_items["item-1"] = document
            return [document]

        with patch(
            "ropa.llm_agents.assistant.assistant.get_retriever",
            return_value=retriever,
        ):
            assistant = Assistant()

        with (
            retriever.override(
                model=FunctionModel(stream_function=retrieval_response),
                tools=[search_catalog],
            ),
            assistant.agent.override(
                model=FunctionModel(stream_function=assistant_response),
            ),
        ):
            output = await assistant.generate("Find a blue shirt", make_deps())

        self.assertEqual(output.recommendations[0].document_id, "item-1")
        self.assertEqual(output.recommendations[0].matches, ("blue",))
        self.assertLessEqual(len(assistant.message_history), 20)
        self.assertEqual(assistant.agent.name, "assistant")
        self.assertEqual(retriever.name, "retriever")

    async def test_retriever_starts_each_run_without_history(self):
        retriever = get_retriever()

        async def retrieval_response(messages, info):
            prompts = [
                part.content
                for message in messages
                for part in message.parts
                if isinstance(part, UserPromptPart)
            ]

            self.assertEqual(len(prompts), 1)
            yield {
                0: DeltaToolCall(
                    name="finish_search",
                    json_args='{"document_ids": []}',
                ),
            }

        with retriever.override(model=FunctionModel(stream_function=retrieval_response)):
            first = await retriever.run("first request", deps=make_deps())
            await retriever.run(
                "second request",
                deps=make_deps(),
                message_history=first.all_messages(),
            )

        self.assertFalse(hasattr(retriever, "message_history"))

    async def test_history_is_bounded_isolated_and_starts_with_user_turn(self):
        assistant = Assistant(max_history_messages=5)
        other = Assistant()
        with assistant.agent.override(model=FunctionModel(stream_function=final_response)):
            for index in range(6):
                await assistant.generate(f"request {index}", make_deps())

        self.assertLessEqual(len(assistant.message_history), 5)
        self.assertEqual(other.message_history, [])
        self.assertIsInstance(assistant.message_history[0], ModelRequest)
        prompts = [
            part.content
            for message in assistant.message_history
            for part in message.parts
            if isinstance(part, UserPromptPart)
        ]

        self.assertEqual(prompts, ["request 5"])

    async def test_failed_run_preserves_history(self):
        assistant = Assistant()
        with assistant.agent.override(model=FunctionModel(stream_function=final_response)):
            await assistant.generate("first request", make_deps())

        history = list(assistant.message_history)
        with patch.object(assistant.agent, "run", side_effect=RuntimeError("model failed")):
            with self.assertRaises(RuntimeError):
                await assistant.generate("failed request", make_deps())

        self.assertEqual(assistant.message_history, history)

    async def test_extractors_return_typed_outputs(self):
        async def color_response(messages, info):
            yield '{"color": "blue"}'

        async def sizes_response(messages, info):
            yield '{"data": [{"size": "M", "chest": 100}]}'

        color_agent = get_garment_color_extractor()
        size_agent = get_size_table_extractor()
        with color_agent.override(model=FunctionModel(stream_function=color_response)):
            async with color_agent.run_stream(
                "color",
                deps=GarmentColorExtractorInput(title="shirt", description="blue"),
            ) as result:
                self.assertEqual((await result.get_output()).color, "blue")

        with size_agent.override(model=FunctionModel(stream_function=sizes_response)):
            async with size_agent.run_stream("sizes") as result:
                self.assertEqual((await result.get_output()).data, [{"size": "M", "chest": 100}])
