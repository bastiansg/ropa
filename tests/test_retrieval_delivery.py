import importlib
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from pydantic_ai import ModelRetry
from telegram.error import BadRequest

from ropa.llm_agents import AssistantDeps, AssistantOutput
from ropa.llm_agents.retrieval_storage import finish_search, read_retrieved_items
from ropa.meta.interfaces import BodyProfile
from ropa.recommendations import RecommendedItem


class RetrievalDeliveryTests(unittest.IsolatedAsyncioTestCase):
    def deps(self):
        return AssistantDeps(
            catalog_schema={}, profile=BodyProfile.model_construct(),
            profile_gender="man", profile_id="profile",
        )

    async def test_cache_access_is_request_scoped_and_checks_expiration(self):
        deps = self.deps()
        ctx = SimpleNamespace(deps=deps)
        with patch("ropa.llm_agents.retrieval_storage.cache") as cache:
            cache.get = AsyncMock(return_value=None)
            with self.assertRaises(ModelRetry):
                await read_retrieved_items(ctx, "another-request")

            cache.get.assert_not_called()
            deps.retrieval_keys.add("expired")
            with self.assertRaisesRegex(ModelRetry, "expired"):
                await read_retrieved_items(ctx, "expired")

    async def test_only_searched_ids_can_be_stored_and_empty_results_are_valid(self):
        ctx = SimpleNamespace(deps=self.deps())
        with patch("ropa.llm_agents.retrieval_storage.cache") as cache:
            cache.set = AsyncMock()
            cache.get = AsyncMock(return_value=[])
            with self.assertRaises(ModelRetry):
                await finish_search(ctx, ["invented"])

            cache.set.assert_not_called()
            result = await finish_search(ctx, [])
            self.assertEqual(result.item_count, 0)
            self.assertEqual(await read_retrieved_items(ctx, result.search_id), [])
            cache.set.assert_awaited_once_with(result.search_id, [], ttl=900)

    async def test_redis_stores_only_ids_and_mongo_restores_ranked_documents(self):
        ctx = SimpleNamespace(deps=self.deps())
        ctx.deps.retrieved_items = {"a": {"_id": "a"}, "b": {"_id": "b"}}
        documents = [{"_id": "b", "title": "current b"}, {"_id": "a", "title": "current a"}]
        with (
            patch("ropa.llm_agents.retrieval_storage.cache") as cache,
            patch("ropa.llm_agents.retrieval_storage.get_mongo_connector") as connector,
        ):
            cache.set = AsyncMock()
            cache.get = AsyncMock(return_value=["a", "b"])
            cursor = connector.return_value.find_multiple.return_value
            cursor.to_list = AsyncMock(return_value=documents)
            result = await finish_search(ctx, ["a", "b", "a"])
            cache.set.assert_awaited_once_with(result.search_id, ["a", "b"], ttl=900)
            self.assertEqual(result.item_count, 2)
            self.assertEqual(await read_retrieved_items(ctx, result.search_id), documents[::-1])
            connector.return_value.find_multiple.assert_called_once_with(
                "catalog_items", filter={"_id": {"$in": ["a", "b"]}},
            )

            cursor.to_list.return_value = documents[:1]
            with self.assertRaisesRegex(ModelRetry, "no longer exist"):
                await read_retrieved_items(ctx, result.search_id)

    async def test_bad_photo_falls_back_to_text_and_continues(self):
        module = importlib.import_module("ropa.telegram_bot.bot.handlers.answer")
        items = [
            RecommendedItem.model_construct(
                title=f"item {index}", gender="unisex", matches=("black",), price=100,
                vendor="Test", url=f"https://example.com/{index}",
                image_urls=(f"https://example.com/{index}.jpg",),
            )
            for index in range(2)
        ]
        assistant = SimpleNamespace(generate=AsyncMock(
            return_value=AssistantOutput.model_construct(recommendations=items),
        ))
        message = SimpleNamespace(
            text="black jeans", reply_text=AsyncMock(),
            reply_photo=AsyncMock(side_effect=[BadRequest("Failed to get http url content"), None]),
        )
        context = SimpleNamespace(chat_data={
            "profile": BodyProfile.model_construct(), "profile_gender": "man",
            "profile_id": "profile", "session_id": "session",
        })
        with (
            patch.object(module, "get_assistant", return_value=assistant),
            patch.object(module, "keep_typing", new=AsyncMock()),
        ):
            await module.answer(SimpleNamespace(message=message, effective_chat=SimpleNamespace(id=1)), context)

        self.assertEqual(message.reply_photo.await_count, 2)
        message.reply_text.assert_awaited_once()
        self.assertIn("https://example.com/0", message.reply_text.call_args.args[0])
        self.assertIn("item 0 // unisex", message.reply_text.call_args.args[0])
