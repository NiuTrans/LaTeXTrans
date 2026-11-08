import asyncio
from datetime import datetime, timezone
import io
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

import aiohttp
import requests
import toml

from src.agents.tool_agents import translator_agent as module
from src.agents.tool_agents.translator_agent import TranslatorAgent
from src.utils.http_retry import is_retryable, retry_delay


def config(limit=10):
    return {"source_language": "en", "target_language": "ch", "llm_config": {
        "model": "test-model", "api_key": "unused", "base_url": "https://example.invalid",
        "timeout": 17, "concurrency_limit": limit,
    }}


def http_error(status=429, headers=None):
    return aiohttp.ClientResponseError(SimpleNamespace(real_url="https://example.invalid"), (),
                                       status=status, headers=headers or {})


class AsyncResponse:
    def __init__(self, error=None):
        self.error = error

    async def __aenter__(self):
        if isinstance(self.error, asyncio.TimeoutError):
            raise self.error
        return self

    async def __aexit__(self, *args):
        return False

    def raise_for_status(self):
        if self.error:
            raise self.error

    async def json(self):
        return {"choices": [{"message": {"content": " translated "}}]}


class FakeSession:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return next(self.responses)


class RetryPolicyTests(unittest.TestCase):
    def test_numeric_date_and_invalid_retry_after(self):
        self.assertEqual(retry_delay(http_error(headers={"Retry-After": "3"}), 1), 3)
        self.assertEqual(retry_delay(http_error(headers={"retry-after": "0"}), 1), 0)
        now = datetime(2015, 10, 21, 7, 28, 10, tzinfo=timezone.utc)
        self.assertEqual(retry_delay(http_error(headers={"Retry-After": "Wed, 21 Oct 2015 07:28:13 GMT"}), 1, now), 3)
        self.assertEqual(retry_delay(http_error(headers={"Retry-After": "Wed, 21 Oct 2015 07:28:00 GMT"}), 1, now), 0)
        for value in ("soon", "-1", "NaN", "inf"):
            with self.subTest(value=value):
                self.assertEqual(retry_delay(http_error(headers={"Retry-After": value}), 2), 10)

    def test_http_status_policy_and_network_errors(self):
        for status in (429, 502, 503, 504):
            self.assertTrue(is_retryable(http_error(status)))
        for status in (400, 401, 403, 404):
            self.assertFalse(is_retryable(http_error(status)))
        self.assertTrue(is_retryable(asyncio.TimeoutError()))
        self.assertTrue(is_retryable(aiohttp.ClientConnectionError()))

    def test_concurrency_default_and_invalid_values(self):
        data = config()
        del data["llm_config"]["concurrency_limit"]
        self.assertEqual(TranslatorAgent(data).concurrency_limit, 10)
        self.assertEqual(TranslatorAgent(config(1)).concurrency_limit, 1)
        for invalid in (0, -1, True, 1.5, "4", None):
            with self.subTest(invalid=invalid):
                with self.assertRaisesRegex(ValueError, "positive integer"):
                    TranslatorAgent(config(invalid))
        public = toml.load(Path(__file__).resolve().parents[1] / "config/default.toml")
        self.assertEqual(public["llm_config"]["concurrency_limit"], 10)


class AsyncRetryTests(unittest.IsolatedAsyncioTestCase):
    async def call_path(self, agent, path, session):
        if path == "plain":
            return await agent._request_llm_for_trans("system", "source", "1", "sec", session)
        if path == "terms":
            return await agent._request_llm_for_trans_with_terms("system", "source", "1", "sec", session)
        if path == "retranslate":
            return await agent._request_llm_for_retrans_error_parts("system", {"content": "source", "trans_content": "previous"}, "error", "1", "sec", session)
        return await agent._request_llm_for_extract_terms("system", "source", "target", session)

    async def test_all_async_paths_honor_retry_after_and_timeout(self):
        for path in ("plain", "terms", "retranslate", "extract"):
            with self.subTest(path=path):
                agent = TranslatorAgent(config())
                session = FakeSession([AsyncResponse(http_error(headers={"Retry-After": "3"})), AsyncResponse()])
                with patch.object(module.asyncio, "sleep", new_callable=AsyncMock) as sleep:
                    self.assertEqual(await self.call_path(agent, path, session), "translated")
                sleep.assert_awaited_once_with(3)
                self.assertEqual(len(session.calls), 2)
                self.assertTrue(all(call[1]["timeout"] == 17 for call in session.calls))
                self.assertFalse(agent.have_fail_parts)

    async def test_backoff_is_bounded_and_exhaustion_preserves_source(self):
        agent = TranslatorAgent(config())
        session = FakeSession([AsyncResponse(http_error()) for _ in range(3)])
        with patch.object(module.asyncio, "sleep", new_callable=AsyncMock) as sleep:
            result = await self.call_path(agent, "plain", session)
        self.assertEqual(result, "source")
        self.assertEqual([call.args[0] for call in sleep.await_args_list], [5, 10])
        self.assertEqual(len(session.calls), 3)
        self.assertEqual(agent.fail_section_nums, ["1"])

    async def test_permanent_error_is_not_retried(self):
        agent = TranslatorAgent(config())
        session = FakeSession([AsyncResponse(http_error(401))])
        with patch.object(module.asyncio, "sleep", new_callable=AsyncMock) as sleep:
            self.assertEqual(await self.call_path(agent, "plain", session), "source")
        sleep.assert_not_awaited()
        self.assertEqual(len(session.calls), 1)

    async def test_timeout_retries_and_retranslation_preserves_previous_on_exhaustion(self):
        agent = TranslatorAgent(config())
        session = FakeSession([AsyncResponse(asyncio.TimeoutError()) for _ in range(3)])
        with patch.object(module.asyncio, "sleep", new_callable=AsyncMock):
            self.assertEqual(await self.call_path(agent, "retranslate", session), "previous")
        self.assertEqual(len(session.calls), 3)

    async def test_execute_applies_configured_concurrency(self):
        agent = TranslatorAgent(config(2), project_dir="project", output_dir="output")
        sections = [{"section": str(i), "content": "source", "trans_content": ""} for i in range(5)]
        active = peak = 0

        async def translate(section, *_):
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(0.01)
            active -= 1
            return section

        with patch.object(agent, "add_placeholder"), patch.object(agent, "build_term_dict"), \
                patch.object(agent, "read_file", side_effect=[sections, [], []]), \
                patch.object(agent, "save_file"), patch.object(agent, "translate", side_effect=translate), \
                patch.object(agent, "_val_fail_parts", new_callable=AsyncMock), \
                patch.object(module.pm, "init_prompts"), patch.object(module, "st", MagicProgress()), \
                patch.object(module, "sys", SimpleNamespace(stderr=sys.stderr, __stderr__=sys.stderr)), \
                patch.object(module, "open", return_value=io.StringIO(), create=True):
            await asyncio.wait_for(agent.execute(), timeout=2)
        self.assertEqual(peak, 2)

    async def test_retranslation_limit_one_completes_all_part_types_without_deadlock(self):
        reports = [{"part": kind, "num_or_ph": identifier} for kind, identifier in (("sec", "1"), ("cap", "C"), ("env", "E"))]
        agent = TranslatorAgent(config(1), errors_report=reports)
        sections, captions, envs = [{"section": "1"}], [{"placeholder": "C"}], [{"placeholder": "E"}]
        active = peak = 0

        async def translate(**kwargs):
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(0.01)
            active -= 1
            part = next(kwargs[name] for name in ("section", "caption", "env") if name in kwargs)
            return dict(part, trans_content="translated")

        with patch.object(agent, "_translate_section", side_effect=translate), \
                patch.object(agent, "_translate_caption", side_effect=translate), \
                patch.object(agent, "_translate_env", side_effect=translate), \
                patch.object(module.time, "sleep"), patch.object(module, "st", MagicProgress()), \
                patch.object(module, "sys", SimpleNamespace(stderr=sys.stderr, __stderr__=sys.stderr)), \
                patch.object(module, "open", return_value=io.StringIO(), create=True):
            await asyncio.wait_for(agent._retranslate_error_parts(sections, captions, envs, None), timeout=2)
        self.assertEqual(peak, 1)
        self.assertTrue(all(part[0]["trans_content"] == "translated" for part in (sections, captions, envs)))


class MagicProgress:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def __getattr__(self, name):
        return lambda *args, **kwargs: self


class SyncRetryTests(unittest.TestCase):
    def test_summary_and_refinement_honor_retry_after(self):
        failure = requests.Response()
        failure.status_code = 429
        failure.headers["Retry-After"] = "7"
        success = Mock()
        success.json.return_value = {"choices": [{"message": {"content": "summary"}}]}
        for refine in (False, True):
            with self.subTest(refine=refine):
                agent = TranslatorAgent(config())
                with patch.object(module.requests, "post", side_effect=[failure, success]) as post, \
                        patch.object(module.time, "sleep") as sleep:
                    if refine:
                        result = agent._request_llm_for_refine_summary("system", "source", "previous")
                    else:
                        result = agent._request_llm_for_summary("system", "source")
                self.assertEqual(result, "summary")
                sleep.assert_called_once_with(7)
                self.assertEqual(post.call_count, 2)
                self.assertEqual(post.call_args.kwargs["timeout"], 17)


if __name__ == "__main__":
    unittest.main()
