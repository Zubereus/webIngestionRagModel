import asyncio
import json
import unittest
from unittest.mock import AsyncMock, patch

from webrag.api.server import (
    AskRequest,
    build_system_prompt,
    context_limit,
    fit_context_blocks,
    has_valid_citations,
    is_explicit_page_question,
    is_small_talk,
    is_vietnamese_text,
    not_found_text,
    should_refuse_without_sources,
    user_language_suffix,
)


class VietnamesePromptTests(unittest.TestCase):
    def test_gemini_3_5_flash_is_the_default_generation_model(self):
        from webrag.api import server

        self.assertEqual(server.DEFAULT_GEN_MODEL, "gemini-3.5-flash")

    def test_detects_vietnamese_question_with_common_diacritics(self):
        self.assertTrue(is_vietnamese_text("mẫu TK01 là tờ khai gì?"))

    def test_does_not_mark_plain_english_as_vietnamese(self):
        self.assertFalse(is_vietnamese_text("What is form TK01?"))

    def test_model_identity_question_is_small_talk_but_document_question_is_not(self):
        self.assertTrue(is_small_talk("What model are you?"))
        self.assertFalse(is_small_talk("Which model does this paper use?"))
        self.assertTrue(is_explicit_page_question("Which model does this paper use?"))

    def test_small_talk_does_not_capture_procedure_questions_or_long_acknowledgements(self):
        for question in (
            "Are you able to tell me the passport fee?",
            "Are you sure it takes 08 days?",
            "Okay, what is the passport fee?",
            "Cool, explain the passport renewal process.",
        ):
            with self.subTest(question=question):
                self.assertFalse(is_small_talk(question))

        for acknowledgement in (
            "ok",
            "ok great",
            "okay, thanks",
            "got it",
            "cool",
            "sounds good",
        ):
            with self.subTest(acknowledgement=acknowledgement):
                self.assertTrue(is_small_talk(acknowledgement))

    def test_context_budget_is_larger_for_gemini_and_keeps_fitting_passages(self):
        self.assertGreater(context_limit("gemini"), context_limit("ollama"))

        blocks = ["a" * 100, "b" * 100, "c" * 100]
        fitted = fit_context_blocks(blocks, 215)

        self.assertEqual(fitted, blocks[:2])
        self.assertLessEqual(len("\n\n---\n\n".join(fitted)), 215)

    def test_vietnamese_prompt_explicitly_sets_response_language(self):
        prompt = build_system_prompt(
            "strict",
            not_found_text("mẫu TK01 là tờ khai gì?"),
            "mẫu TK01 là tờ khai gì?",
            "qwen2.5:3b",
        )

        self.assertIn("Chỉ trả lời bằng tiếng Việt", prompt)
        self.assertIn("không dùng tiếng Trung", prompt)
        self.assertIn("exact value and unit", prompt)
        self.assertEqual(
            user_language_suffix("Thời gian cấp hộ chiếu là bao lâu?"),
            "Hãy trả lời hoàn toàn bằng tiếng Việt.",
        )

    def test_gemini_strict_prompt_is_task_specific_and_not_qwen_guardrails(self):
        prompt = build_system_prompt(
            "strict",
            "Your saved pages don't answer this.",
            "What is the processing time?",
            "gemini-3.5-flash",
        )

        self.assertIn("Procedure and Section", prompt)
        self.assertIn("each variant separately", prompt)
        self.assertIn("Reply in the language of the question", prompt)
        self.assertIn("boolean `answerable` and string `answer`", prompt)
        self.assertIn("clearly identify what is missing", prompt)
        self.assertNotIn("NGÔN NGỮ BẮT BUỘC", prompt)
        self.assertNotIn("Do not switch to Chinese", prompt)

    def test_gemini_broad_summary_prompt_requests_complete_cited_synthesis(self):
        prompt = build_system_prompt(
            "strict",
            "Your saved pages don't answer this.",
            "What are the key points in this paper?",
            "gemini-3.5-flash",
        )

        self.assertIn("5-7 numbered points", prompt)
        self.assertIn("250-400 words", prompt)
        self.assertIn("Do not stop after the opening overview or first heading", prompt)

    def test_gemini_summary_guidance_does_not_change_focused_questions(self):
        prompt = build_system_prompt(
            "strict",
            "Your saved pages don't answer this.",
            "What is the processing time?",
            "gemini-3.5-flash",
        )

        self.assertNotIn("250-400 words", prompt)

    def test_substantive_question_without_passages_is_refused(self):
        self.assertTrue(
            should_refuse_without_sources(
                "Thời gian cấp hộ chiếu là bao lâu?", []
            )
        )

    def test_small_talk_without_passages_can_still_be_chat(self):
        self.assertFalse(should_refuse_without_sources("Xin chào", []))
        self.assertFalse(
            should_refuse_without_sources(
                "Thời gian cấp hộ chiếu là bao lâu?", [{"chunk_id": "page:0"}]
            )
        )

    def test_chat_tokens_are_streamed_as_they_arrive(self):
        from webrag.api import server

        class FakeResponse:
            def raise_for_status(self):
                return None

            async def aiter_lines(self):
                yield json.dumps({"message": {"content": "Xin "}})
                yield json.dumps({"message": {"content": "chào!"}})
                yield json.dumps({"done": True, "prompt_eval_count": 12})

        class FakeStream:
            async def __aenter__(self):
                return FakeResponse()

            async def __aexit__(self, exc_type, exc_value, traceback):
                return False

        class FakeClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_value, traceback):
                return False

            def stream(self, *args, **kwargs):
                return FakeStream()

        async def collect_events():
            response = await server.ask_stream(
                AskRequest(
                    question="Xin chào",
                    scope_doc_ids=["saved-page"],
                    model="qwen2.5:3b",
                )
            )
            return "".join([event async for event in response.body_iterator])

        with (
            patch("webrag.api.server.find_chunks") as find_chunks,
            patch(
                "webrag.api.server.httpx.AsyncClient",
                return_value=FakeClient(),
            ),
        ):
            events = asyncio.run(collect_events())

        find_chunks.assert_not_called()
        token_data = [
            json.loads(block.split("data: ", 1)[1])["text"]
            for block in events.split("\n\n")
            if block.startswith("event: token\n")
        ]
        self.assertEqual(token_data, ["Xin ", "chào!"])

    def test_gemini_answers_model_identity_even_with_selected_pages(self):
        from webrag.api import server

        request_details = {}

        class FakeResponse:
            def raise_for_status(self):
                return None

            async def aiter_lines(self):
                yield "data: " + json.dumps(
                    {
                        "candidates": [{
                            "content": {
                                "parts": [{"text": "I am Gemini 3.5 Flash."}]
                            }
                        }]
                    }
                )

        class FakeStream:
            async def __aenter__(self):
                return FakeResponse()

            async def __aexit__(self, exc_type, exc_value, traceback):
                return False

        class FakeClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_value, traceback):
                return False

            def stream(self, method, url, **kwargs):
                request_details.update(method=method, url=url, **kwargs)
                return FakeStream()

        async def collect_events():
            response = await server.ask_stream(
                AskRequest(
                    question="What model are you?",
                    model="gemini-3.5-flash",
                    scope_doc_ids=["saved-page"],
                )
            )
            return "".join([event async for event in response.body_iterator])

        with (
            patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}),
            patch("webrag.api.server.find_chunks") as find_chunks,
            patch("webrag.api.server.httpx.AsyncClient", return_value=FakeClient()),
        ):
            events = asyncio.run(collect_events())

        find_chunks.assert_not_called()
        system_prompt = request_details["json"]["systemInstruction"]["parts"][0]["text"]
        self.assertIn("Gemini 3.5 Flash", system_prompt)
        self.assertIn("event: token", events)

    def test_qwen3_request_disables_thinking_and_uses_selected_model(self):
        from webrag.api import server

        request_details = {}

        class FakeResponse:
            def raise_for_status(self):
                return None

            async def aiter_lines(self):
                yield json.dumps({"message": {"content": "Xin chào"}})
                yield json.dumps({"done": True})

        class FakeStream:
            async def __aenter__(self):
                return FakeResponse()

            async def __aexit__(self, exc_type, exc_value, traceback):
                return False

        class FakeClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_value, traceback):
                return False

            def stream(self, method, url, **kwargs):
                request_details.update(method=method, url=url, **kwargs)
                return FakeStream()

        async def collect_events():
            response = await server.ask_stream(
                AskRequest(question="Xin chào", model="qwen3:4b")
            )
            return "".join([event async for event in response.body_iterator])

        with (
            patch("webrag.api.server.find_chunks", return_value=[]),
            patch("webrag.api.server.httpx.AsyncClient", return_value=FakeClient()),
        ):
            events = asyncio.run(collect_events())

        self.assertIn("event: token", events)
        self.assertEqual(request_details["json"]["model"], "qwen3:4b")
        self.assertIs(request_details["json"]["think"], False)
        self.assertEqual(request_details["json"]["options"]["num_ctx"], 4096)

    def test_ollama_retrieval_skips_cpu_reranking(self):
        from webrag.api import server

        source = {
            "chunk_id": "page:0",
            "text": "The saved page explains the procedure.",
            "metadata": {
                "doc_id": "page",
                "title": "Procedure",
                "section_path": "Overview",
                "url": "https://example.test/procedure",
            },
            "dense_score": 0.8,
            "bm25_score": 8.0,
            "score": 0.8,
        }

        class FakeResponse:
            def raise_for_status(self):
                return None

            async def aiter_lines(self):
                yield json.dumps({"message": {"content": "The page explains it [1]."}})
                yield json.dumps({"done": True})

        class FakeStream:
            async def __aenter__(self):
                return FakeResponse()

            async def __aexit__(self, exc_type, exc_value, traceback):
                return False

        class FakeClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_value, traceback):
                return False

            def stream(self, *args, **kwargs):
                return FakeStream()

        async def collect_events():
            response = await server.ask_stream(
                AskRequest(question="What does the page explain?", model="qwen3:4b")
            )
            return "".join([event async for event in response.body_iterator])

        with (
            patch(
                "webrag.api.server.find_chunks", return_value=[source]
            ) as find_chunks,
            patch("webrag.api.server.rerank_chunks") as rerank,
            patch(
                "webrag.api.server.httpx.AsyncClient",
                return_value=FakeClient(),
            ),
        ):
            events = asyncio.run(collect_events())

        self.assertEqual(find_chunks.call_args.kwargs["top_k"], 5)
        rerank.assert_not_called()
        self.assertIn("event: token", events)

    def test_gemini_request_uses_server_key_and_streams_text(self):
        from webrag.api import server

        request_details = {}

        class FakeResponse:
            def raise_for_status(self):
                return None

            async def aiter_lines(self):
                yield 'data: {"candidates":[{"content":{"parts":[{"text":"Hello"}]}}]}'

        class FakeStream:
            async def __aenter__(self):
                return FakeResponse()

            async def __aexit__(self, exc_type, exc_value, traceback):
                return False

        class FakeClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_value, traceback):
                return False

            def stream(self, method, url, **kwargs):
                request_details.update(method=method, url=url, **kwargs)
                return FakeStream()

        async def collect_events():
            response = await server.ask_stream(
                AskRequest(question="Hello", model="gemini-2.5-flash")
            )
            return "".join([event async for event in response.body_iterator])

        with (
            patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}),
            patch("webrag.api.server.find_chunks", return_value=[]),
            patch("webrag.api.server.httpx.AsyncClient", return_value=FakeClient()),
        ):
            events = asyncio.run(collect_events())

        self.assertIn("event: token\ndata: {\"text\": \"Hello\"}", events)
        self.assertIn("gemini-2.5-flash:streamGenerateContent", request_details["url"])
        self.assertEqual(request_details["headers"]["x-goog-api-key"], "test-key")
        self.assertNotIn("test-key", request_details["url"])

    def test_gemini_requires_a_server_api_key(self):
        from fastapi import HTTPException
        from webrag.api import server

        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(HTTPException) as raised:
                asyncio.run(
                    server.ask_stream(
                        AskRequest(question="Hello", model="gemini-2.5-flash")
                    )
                )
        self.assertEqual(raised.exception.status_code, 503)

    def test_gemini_3_5_flash_is_allowlisted_and_uses_its_model_endpoint(self):
        from webrag.api import server

        model = next(
            (item for item in server.MODEL_OPTIONS if item["id"] == "gemini-3.5-flash"),
            None,
        )
        self.assertIsNotNone(model)
        self.assertEqual(model["label"], "Gemini 3.5 Flash")

        request_details = {}

        class FakeResponse:
            def raise_for_status(self):
                return None

            async def aiter_lines(self):
                yield (
                    'data: {"candidates":[{"content":{"parts":[{"text":"Hello"}]},'
                    '"finishReason":"STOP"}],"usageMetadata":{"promptTokenCount":12}}'
                )

        class FakeStream:
            async def __aenter__(self):
                return FakeResponse()

            async def __aexit__(self, exc_type, exc_value, traceback):
                return False

        class FakeClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_value, traceback):
                return False

            def stream(self, method, url, **kwargs):
                request_details.update(method=method, url=url, **kwargs)
                return FakeStream()

        async def collect_events():
            response = await server.ask_stream(
                AskRequest(question="Hello", model="gemini-3.5-flash")
            )
            return "".join([event async for event in response.body_iterator])

        with self.assertLogs("webrag.api.server", level="INFO") as logs:
            with (
                patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}),
                patch("webrag.api.server.find_chunks", return_value=[]),
                patch("webrag.api.server.httpx.AsyncClient", return_value=FakeClient()),
            ):
                events = asyncio.run(collect_events())

        self.assertIn("event: token", events)
        self.assertIn("gemini-3.5-flash:streamGenerateContent", request_details["url"])
        self.assertEqual(request_details["headers"]["x-goog-api-key"], "test-key")
        self.assertEqual(
            request_details["json"]["generationConfig"]["maxOutputTokens"],
            1500,
        )
        self.assertNotIn(
            "temperature",
            request_details["json"]["generationConfig"],
        )
        self.assertTrue(any("finish_reason=STOP" in message for message in logs.output))
        self.assertTrue(any("prompt_tokens=12" in message for message in logs.output))

    def test_gemini_receives_and_can_cite_relevant_tenth_passage(self):
        from webrag.api import server

        chunks = [
            {
                "chunk_id": f"yolo:{index}",
                "text": (
                    "Background discussion. " * 35
                    if index < 9
                    else "YOLO26 removes DFL and supports native NMS-free inference."
                ),
                "metadata": {
                    "doc_id": "yolo",
                    "title": "YOLO detector overview",
                    "section_path": f"Section {index}",
                    "url": "https://example.test/yolo",
                },
                "dense_score": 0.8,
                "bm25_score": 7.0,
                "score": 0.8,
            }
            for index in range(10)
        ]
        request_details = {}

        class FakeResponse:
            def raise_for_status(self):
                return None

            async def aiter_lines(self):
                yield (
                    'data: {"candidates":[{"content":{"parts":[{"text":'
                    '"{\\"answerable\\":true,\\"answer\\":'
                    '\\"YOLO26 removes DFL and supports native NMS-free inference [1].\\"}"}]},'
                    '"finishReason":"STOP"}]}'
                )

        class FakeStream:
            async def __aenter__(self):
                return FakeResponse()

            async def __aexit__(self, exc_type, exc_value, traceback):
                return False

        class FakeClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_value, traceback):
                return False

            def stream(self, method, url, **kwargs):
                request_details.update(method=method, url=url, **kwargs)
                return FakeStream()

        async def collect_events():
            response = await server.ask_stream(
                AskRequest(
                    question="What features does YOLO26 have?",
                    model="gemini-3.5-flash",
                    scope_doc_ids=["yolo"],
                )
            )
            return "".join([event async for event in response.body_iterator])

        with (
            patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}),
            patch("webrag.api.server.RERANKER_ENABLED", True),
            patch(
                "webrag.api.server.find_chunks", return_value=chunks
            ) as find_chunks,
            patch(
                "webrag.api.server.keep_relevant", return_value=[]
            ) as relevance_gate,
            patch(
                "webrag.api.server.rerank_chunks",
                side_effect=lambda question, candidates, top_n, device: [
                    candidates[-1], *candidates[:-1]
                ][:top_n],
            ) as rerank,
            patch("webrag.api.server.reranker_device", return_value="cpu"),
            patch("webrag.api.server.context_limit", return_value=30000),
            patch("webrag.api.server.httpx.AsyncClient", return_value=FakeClient()),
        ):
            events = asyncio.run(collect_events())

        self.assertEqual(find_chunks.call_args.kwargs["top_k"], 12)
        rerank.assert_called_once_with(
            "What features does YOLO26 have?", chunks, 8, "cpu"
        )
        relevance_gate.assert_not_called()
        user_content = request_details["json"]["contents"][-1]["parts"][0]["text"]
        self.assertIn('<passage id="1">', user_content)
        self.assertIn("Procedure: YOLO detector overview", user_content)
        self.assertIn("Section: Section 9", user_content)
        self.assertIn(
            "YOLO26 removes DFL and supports native NMS-free inference.",
            user_content,
        )
        self.assertIn("event: token", events)
        self.assertNotIn("I couldn't verify a synthesized answer", events)
        generation_config = request_details["json"]["generationConfig"]
        self.assertEqual(generation_config["responseMimeType"], "application/json")
        self.assertEqual(
            generation_config["responseSchema"],
            {
                "type": "OBJECT",
                "properties": {
                    "answerable": {"type": "BOOLEAN"},
                    "answer": {"type": "STRING"},
                },
                "required": ["answerable", "answer"],
            },
        )
        retrieved_event = next(
            block for block in events.split("\n\n")
            if block.startswith("event: retrieved\n")
        )
        retrieved = json.loads(retrieved_event.split("data: ", 1)[1])
        self.assertEqual(len(retrieved), 8)

    def test_gemini_structured_refusal_and_invalid_json_handling(self):
        from webrag.api import server

        source = {
            "chunk_id": "passport:1",
            "text": "Processing takes 8 working days.",
            "metadata": {
                "doc_id": "passport",
                "title": "Passport",
                "section_path": "Processing time",
                "url": "https://example.test/passport",
            },
            "dense_score": 0.8,
            "bm25_score": 7.0,
            "score": 0.8,
        }

        class FakeResponse:
            def __init__(self, text):
                self.text = text

            def raise_for_status(self):
                return None

            async def aiter_lines(self):
                yield "data: " + json.dumps(
                    {
                        "candidates": [
                            {"content": {"parts": [{"text": self.text}]}}
                        ]
                    }
                )

        class FakeStream:
            def __init__(self, text):
                self.response = FakeResponse(text)

            async def __aenter__(self):
                return self.response

            async def __aexit__(self, exc_type, exc_value, traceback):
                return False

        class FakeClient:
            def __init__(self, text):
                self.text = text

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_value, traceback):
                return False

            def stream(self, *args, **kwargs):
                return FakeStream(self.text)

        async def collect_events(text):
            response = await server.ask_stream(
                AskRequest(
                    question="What is the processing time?",
                    collection="immigration",
                    model="gemini-3.5-flash",
                )
            )
            return "".join([event async for event in response.body_iterator])

        scenarios = (
            (
                json.dumps({"answerable": False, "answer": "Unsupported."}),
                "event: not_found",
            ),
            ("not valid JSON", "I couldn't verify a synthesized answer."),
        )
        for response_text, expected in scenarios:
            with self.subTest(response_text=response_text):
                with (
                    patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}),
                    patch("webrag.api.server.RERANKER_ENABLED", False),
                    patch("webrag.api.server.find_chunks", return_value=[source]),
                    patch("webrag.api.server.keep_relevant", return_value=[source]),
                    patch(
                        "webrag.api.server.httpx.AsyncClient",
                        return_value=FakeClient(response_text),
                    ),
                ):
                    events = asyncio.run(collect_events(response_text))
                self.assertIn(expected, events)
                if expected == "event: not_found":
                    self.assertNotIn("event: token", events)
                else:
                    self.assertIn("event: token", events)

    def test_gemini_http_errors_show_provider_detail_without_excerpt_fallback(self):
        import httpx
        from webrag.api import server

        class FakeResponse:
            def __init__(self):
                self.response = httpx.Response(
                    403,
                    json={
                        "error": {
                            "code": 403,
                            "message": "API key does not have access to this model.",
                            "status": "PERMISSION_DENIED",
                        }
                    },
                    request=httpx.Request(
                        "POST",
                        "https://generativelanguage.googleapis.com/v1beta/test",
                    ),
                )

            def raise_for_status(self):
                self.response.raise_for_status()

            async def aread(self):
                return await self.response.aread()

            @property
            def text(self):
                return self.response.text

            @property
            def reason_phrase(self):
                return self.response.reason_phrase

            @property
            def status_code(self):
                return self.response.status_code

            def json(self):
                return self.response.json()

        class FakeStream:
            async def __aenter__(self):
                return FakeResponse()

            async def __aexit__(self, exc_type, exc_value, traceback):
                return False

        class FakeClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_value, traceback):
                return False

            def stream(self, *args, **kwargs):
                return FakeStream()

        source = {
            "chunk_id": "passport:1",
            "text": "Processing takes 8 working days.",
            "metadata": {
                "doc_id": "passport",
                "title": "Passport",
                "url": "https://example.test/passport",
            },
            "dense_score": 0.8,
            "bm25_score": 5.0,
            "score": 0.02,
        }

        async def collect_events():
            response = await server.ask_stream(
                AskRequest(question="What is the deadline?", model="gemini-3.5-flash")
            )
            return "".join([event async for event in response.body_iterator])

        with (
            patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}),
            patch("webrag.api.server.find_chunks", return_value=[source]),
            patch("webrag.api.server.keep_relevant", return_value=[source]),
            patch("webrag.api.server.prioritize_qualified_chunks", return_value=[source]),
            patch(
                "webrag.api.server.build_sources",
                return_value=([], [], ["source context"]),
            ),
            patch("webrag.api.server.httpx.AsyncClient", return_value=FakeClient()),
        ):
            events = asyncio.run(collect_events())

        self.assertIn("Gemini API returned HTTP 403", events)
        self.assertIn("API key does not have access to this model.", events)
        self.assertNotIn("event: token", events)
        self.assertNotIn("event: not_found", events)
        self.assertNotIn("event: done", events)
        self.assertNotIn("test-key", events)

    def test_gemini_retries_transient_503_then_returns_success(self):
        import httpx
        from webrag.api import server

        calls = 0

        class FakeResponse:
            def __init__(self, response, lines=()):
                self.response = response
                self.lines = lines

            def raise_for_status(self):
                self.response.raise_for_status()

            async def aread(self):
                return await self.response.aread()

            async def aiter_lines(self):
                for line in self.lines:
                    yield line

            @property
            def status_code(self):
                return self.response.status_code

            @property
            def headers(self):
                return self.response.headers

            @property
            def text(self):
                return self.response.text

            @property
            def reason_phrase(self):
                return self.response.reason_phrase

            def json(self):
                return self.response.json()

        class FakeStream:
            def __init__(self, response):
                self.response = response

            async def __aenter__(self):
                return self.response

            async def __aexit__(self, exc_type, exc_value, traceback):
                return False

        class FakeClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_value, traceback):
                return False

            def stream(self, *args, **kwargs):
                nonlocal calls
                calls += 1
                request = httpx.Request(
                    "POST", "https://generativelanguage.googleapis.com/v1beta/test"
                )
                if calls == 1:
                    response = httpx.Response(
                        503,
                        json={
                            "error": {
                                "message": "This model is currently experiencing high demand."
                            }
                        },
                        request=request,
                    )
                    return FakeStream(FakeResponse(response))

                response = httpx.Response(200, request=request)
                result = json.dumps(
                    {
                        "candidates": [
                            {
                                "content": {
                                    "parts": [
                                        {
                                            "text": json.dumps(
                                                {
                                                    "answerable": False,
                                                    "answer": "Your saved pages don't answer this.",
                                                }
                                            )
                                        }
                                    ]
                                }
                            }
                        ]
                    }
                )
                return FakeStream(
                    FakeResponse(response, [f"data: {result}"])
                )

        async def collect_events():
            response = await server.ask_stream(
                AskRequest(
                    question="What is the processing time?",
                    model="gemini-3.5-flash",
                )
            )
            return "".join([event async for event in response.body_iterator])

        with (
            patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}),
            patch("webrag.api.server.RERANKER_ENABLED", False),
            patch(
                "webrag.api.server.find_chunks",
                return_value=[
                    {
                        "chunk_id": "passport:1",
                        "text": "Processing takes 8 working days.",
                        "metadata": {
                            "doc_id": "passport",
                            "title": "Passport",
                            "url": "https://example.test/passport",
                        },
                        "dense_score": 0.8,
                        "bm25_score": 7.0,
                        "score": 0.8,
                    }
                ],
            ),
            patch(
                "webrag.api.server.keep_relevant",
                side_effect=lambda chunks, wants_pages: chunks,
            ),
            patch(
                "webrag.api.server.build_sources",
                return_value=([], [], ["source context"]),
            ),
            patch("webrag.api.server.httpx.AsyncClient", return_value=FakeClient()),
            patch("webrag.api.server.asyncio.sleep", new_callable=AsyncMock),
        ):
            events = asyncio.run(collect_events())

        self.assertEqual(calls, 2)
        self.assertIn("Gemini is busy; retrying (1/2)", events)
        self.assertIn("event: not_found", events)
        self.assertNotIn("event: error", events)

    def test_gemini_connection_errors_include_provider_and_network_guidance(self):
        import httpx
        from webrag.api import server

        request = httpx.Request(
            "POST",
            "https://generativelanguage.googleapis.com/v1beta/test",
        )

        class FakeStream:
            async def __aenter__(self):
                raise httpx.ConnectError("network error", request=request)

            async def __aexit__(self, exc_type, exc_value, traceback):
                return False

        class FakeClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_value, traceback):
                return False

            def stream(self, *args, **kwargs):
                return FakeStream()

        async def collect_events():
            response = await server.ask_stream(
                AskRequest(question="Hello", model="gemini-3.5-flash")
            )
            return "".join([event async for event in response.body_iterator])

        with (
            patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}),
            patch("webrag.api.server.find_chunks", return_value=[]),
            patch("webrag.api.server.httpx.AsyncClient", return_value=FakeClient()),
        ):
            events = asyncio.run(collect_events())

        self.assertIn("Could not connect to Gemini API (ConnectError)", events)
        self.assertIn("Check the backend's internet connection", events)
        self.assertNotIn("test-key", events)
        self.assertNotIn("event: done", events)

    def test_substantive_question_without_results_returns_not_found_without_llm(self):
        from webrag.api import server

        async def collect_events():
            response = await server.ask_stream(
                AskRequest(
                    question="Thời gian cấp hộ chiếu là bao lâu?",
                    model="qwen2.5:3b",
                )
            )
            return "".join([event async for event in response.body_iterator])

        with (
            patch("webrag.api.server.find_chunks", return_value=[]),
            patch("webrag.api.server.httpx.AsyncClient") as ollama_client,
        ):
            events = asyncio.run(collect_events())

        self.assertIn("event: not_found", events)
        payloads = [
            json.loads(line.removeprefix("data: "))
            for line in events.splitlines()
            if line.startswith("data: ")
        ]
        self.assertIn(
            "Các trang đã lưu không trả lời được câu hỏi này.",
            [payload.get("message") for payload in payloads],
        )
        ollama_client.assert_not_called()

    def test_model_refusal_returns_not_found_instead_of_excerpt(self):
        from webrag.api import server

        source = {
            "chunk_id": "passport:13",
            "text": "Người đề nghị nộp tờ khai TK01 và bản sao giấy tờ tùy thân.",
            "metadata": {
                "doc_id": "passport",
                "title": "Cấp hộ chiếu phổ thông ở trong nước",
                "section_path": "Thành phần hồ sơ",
                "url": "https://example.test/passport",
            },
            "dense_score": 0.76,
            "bm25_score": 8.0,
            "score": 0.03,
        }

        class FakeResponse:
            def raise_for_status(self):
                return None

            async def aiter_lines(self):
                yield json.dumps({
                    "message": {
                        "content": "Các trang đã lưu không trả lời "
                    }
                })
                yield json.dumps({"message": {"content": "được câu hỏi này."}})
                yield json.dumps({"done": True, "prompt_eval_count": 20})

        class FakeStream:
            async def __aenter__(self):
                return FakeResponse()

            async def __aexit__(self, exc_type, exc_value, traceback):
                return False

        class FakeClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_value, traceback):
                return False

            def stream(self, *args, **kwargs):
                return FakeStream()

        async def collect_events():
            response = await server.ask_stream(AskRequest(
                question="Cần nộp giấy tờ gì để xin cấp hộ chiếu?",
                collection="immigration",
                scope_doc_ids=["passport"],
                top_k=10,
                model="qwen2.5:3b",
            ))
            return "".join([event async for event in response.body_iterator])

        with (
            patch(
                "webrag.api.server.find_chunks",
                return_value=[source],
            ),
            patch(
                "webrag.api.server.httpx.AsyncClient",
                return_value=FakeClient(),
            ) as ollama_client,
        ):
            events = asyncio.run(collect_events())

        token_data = [
            json.loads(block.split("data: ", 1)[1])["text"]
            for block in events.split("\n\n")
            if block.startswith("event: token\n")
        ]
        self.assertEqual(token_data, [])
        self.assertIn("event: not_found", events)
        self.assertNotIn("Đoạn nguồn phù hợp nhất", events)
        self.assertIn("event: citations", events)
        ollama_client.assert_called_once()

    def test_invalid_citations_still_fall_back_to_relevant_excerpt(self):
        from webrag.api import server

        source = {
            "chunk_id": "passport:13",
            "text": "Người đề nghị nộp tờ khai TK01 và bản sao giấy tờ tùy thân.",
            "metadata": {
                "doc_id": "passport",
                "title": "Cấp hộ chiếu phổ thông ở trong nước",
                "section_path": "Thành phần hồ sơ",
                "url": "https://example.test/passport",
            },
            "dense_score": 0.76,
            "bm25_score": 8.0,
            "score": 0.03,
        }

        class FakeResponse:
            def raise_for_status(self):
                return None

            async def aiter_lines(self):
                yield json.dumps({"message": {"content": "The answer is 42 [99]."}})
                yield json.dumps({"done": True, "prompt_eval_count": 20})

        class FakeStream:
            async def __aenter__(self):
                return FakeResponse()

            async def __aexit__(self, exc_type, exc_value, traceback):
                return False

        class FakeClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_value, traceback):
                return False

            def stream(self, *args, **kwargs):
                return FakeStream()

        async def collect_events():
            response = await server.ask_stream(AskRequest(
                question="Cần nộp giấy tờ gì để xin cấp hộ chiếu?",
                collection="immigration",
                scope_doc_ids=["passport"],
                model="qwen2.5:3b",
            ))
            return "".join([event async for event in response.body_iterator])

        with (
            patch("webrag.api.server.find_chunks", return_value=[source]),
            patch(
                "webrag.api.server.httpx.AsyncClient",
                return_value=FakeClient(),
            ),
        ):
            events = asyncio.run(collect_events())

        token_data = [
            json.loads(block.split("data: ", 1)[1])["text"]
            for block in events.split("\n\n")
            if block.startswith("event: token\n")
        ]
        self.assertEqual(len(token_data), 1)
        self.assertIn("Đoạn nguồn phù hợp nhất", token_data[0])
        self.assertIn("tờ khai TK01", token_data[0])
        self.assertNotIn("event: not_found", events)

    def test_excerpt_fallback_prefers_matching_procedure_and_heading(self):
        from webrag.api.server import evidence_excerpt_answer

        question = (
            "Thời gian cấp hộ chiếu cho người đủ 14 tuổi trở lên "
            "(thực hiện tại cấp tỉnh)"
        )
        chunks = [
            {
                "text": "160.000 đồng/hộ chiếu.",
                "metadata": {
                    "title": (
                        "Cấp hộ chiếu phổ thông ở trong nước "
                        "(thực hiện tại cấp tỉnh)"
                    ),
                    "section_path": (
                        "LĨNH VỰC TTHC > Cấp hộ chiếu phổ thông ở trong nước "
                        "(thực hiện tại cấp tỉnh)"
                    ),
                },
            },
            {
                "text": "03 Ngày làm việc.",
                "metadata": {
                    "title": (
                        "Cấp hộ chiếu phổ thông ở trong nước "
                        "(thực hiện tại cấp trung ương)"
                    ),
                    "section_path": "Thời hạn giải quyết",
                },
            },
            {
                "text": "08 Ngày làm việc.",
                "metadata": {
                    "title": (
                        "Cấp hộ chiếu phổ thông ở trong nước "
                        "(thực hiện tại cấp tỉnh)"
                    ),
                    "section_path": "Thời hạn giải quyết",
                },
            },
        ]

        answer = evidence_excerpt_answer(question, chunks)

        self.assertIn("08 Ngày làm việc", answer)
        self.assertIn("[3]", answer)
        self.assertNotIn("03 Ngày làm việc", answer)

    def test_duration_fallback_prefers_passage_with_duration_value(self):
        from webrag.api.server import evidence_excerpt_answer

        title = (
            "Cấp hộ chiếu phổ thông ở trong nước "
            "(thực hiện tại cấp tỉnh)"
        )
        chunks = [
            {
                "text": "160.000 đồng/hộ chiếu.",
                "metadata": {
                    "title": title,
                    "section_path": f"LĨNH VỰC TTHC > {title}",
                },
            },
            {
                "text": "Tờ khai đề nghị cấp hộ chiếu phổ thông.",
                "metadata": {
                    "title": title,
                    "section_path": "Thành phần hồ sơ",
                },
            },
            {
                "text": "Trường hợp hồ sơ thiếu thì cán bộ hướng dẫn bổ sung.",
                "metadata": {
                    "title": title,
                    "section_path": "Trình tự thực hiện",
                },
            },
            {
                "text": (
                    "Thời gian trả hộ chiếu: từ thứ 2 đến thứ 6. "
                    "Thời hạn giải quyết là 08 Ngày làm việc."
                ),
                "metadata": {
                    "title": title,
                    "section_path": f"LĨNH VỰC TTHC > {title}",
                },
            },
        ]

        answer = evidence_excerpt_answer(
            "Thời gian cấp hộ chiếu cho người đủ 14 tuổi trở lên "
            "(thực hiện tại cấp tỉnh) là bao lâu?",
            chunks,
        )

        self.assertIn("08 Ngày làm việc", answer)
        self.assertIn("[4]", answer)

    def test_citations_must_match_explicit_procedure_qualifier(self):
        from webrag.api.server import prioritize_qualified_chunks

        question = (
            "Thời gian cấp hộ chiếu cho người đủ 14 tuổi trở lên "
            "(thực hiện tại cấp tỉnh)"
        )
        citations = [
            {"title": "Cấp hộ chiếu phổ thông ở trong nước (thực hiện tại cấp trung ương)"},
            {"title": "Cấp hộ chiếu phổ thông ở trong nước (thực hiện tại cấp tỉnh)"},
        ]
        chunks = [
            {"text": "Thời hạn giải quyết là 03 Ngày làm việc."},
            {"text": "Thời hạn giải quyết là 08 Ngày làm việc."},
        ]

        self.assertFalse(
            has_valid_citations("03 ngày [1]", citations, question, chunks)
        )
        self.assertTrue(
            has_valid_citations("08 ngày làm việc [2]", citations, question, chunks)
        )
        self.assertFalse(
            has_valid_citations("03 đến 05 ngày [2]", citations, question, chunks)
        )
        self.assertFalse(
            has_valid_citations("08 ngày [8]", citations, question, chunks)
        )
        self.assertFalse(
            has_valid_citations("08 ngày [2] [8]", citations, question, chunks)
        )
        self.assertTrue(
            has_valid_citations(
                "The deadline is 08 working days [2, 1]",
                citations,
                "What is the deadline?",
                chunks,
            )
        )
        self.assertTrue(
            has_valid_citations(
                "Thời gian từ 03 đến 08 ngày [2]",
                citations,
                question,
                [
                    {"text": "Không liên quan."},
                    {"text": "Thời hạn giải quyết từ 03 đến 08 ngày làm việc."},
                ],
            )
        )
        self.assertFalse(
            has_valid_citations(
                "Thời gian từ 03 đến 08 ngày [2]",
                citations,
                question,
                [
                    {"text": "Không liên quan."},
                    {
                        "text": (
                            "03 ngày tiếp nhận hồ sơ; "
                            "thời hạn giải quyết là 08 ngày."
                        )
                    },
                ],
            )
        )

        chunks = [
            {"metadata": {"title": "Cấp hộ chiếu ở cấp trung ương"}},
            {"metadata": {"title": "Cấp hộ chiếu ở cấp tỉnh"}},
        ]
        self.assertEqual(
            prioritize_qualified_chunks(question, chunks),
            [chunks[1], chunks[0]],
        )

    def test_vietnamese_questions_use_vietnamese_not_found_text(self):
        self.assertEqual(
            not_found_text("mẫu TK01 là tờ khai gì?"),
            "Các trang đã lưu không trả lời được câu hỏi này.",
        )


if __name__ == "__main__":
    unittest.main()
