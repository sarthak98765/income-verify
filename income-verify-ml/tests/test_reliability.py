"""Fallback model and Langfuse trace events. The model call is mocked; no network."""
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
import ai_client
import tracing
import usage


def failing_on(bad_model):
    async def call(model, *args, **kwargs):
        if model == bad_model:
            raise RuntimeError("503 service unavailable")
        return {"ok": model}
    return call


@patch.object(ai_client, "OPENAI_API_KEY", "test-key")
@patch.object(ai_client, "LLM_RETRY_ATTEMPTS", 2)
@patch.object(ai_client.asyncio, "sleep", AsyncMock())
class Fallback(unittest.IsolatedAsyncioTestCase):
    async def test_outage_on_the_main_model_falls_back_and_is_counted(self):
        tally = usage.start()
        with patch.object(ai_client, "call_model", side_effect=failing_on("gpt-6.1-terra")):
            out = await ai_client.get_ai_output("system", "user", model="gpt-6.1-terra", name="extract_payslip")
        self.assertEqual((out, tally.as_doc()["fallbacks"]), ({"ok": "gpt-6.1-sol"}, 1))

    async def test_truncation_does_not_fall_back(self):
        # A cut-off reply means "send less"; another model would be cut off too.
        model = AsyncMock(side_effect=ai_client.TruncatedResponse("too long"))
        with patch.object(ai_client, "call_model", model):
            with self.assertRaises(ai_client.TruncatedResponse):
                await ai_client.get_ai_output("system", "user", model="gpt-6.1-terra")
        self.assertEqual(model.await_count, 1)

    async def test_both_models_down_raises(self):
        with patch.object(ai_client, "call_model", AsyncMock(side_effect=RuntimeError("down"))):
            with self.assertRaises(RuntimeError):
                await ai_client.get_ai_output("system", "user", model="gpt-6-luna")


class TraceEvents(unittest.TestCase):
    def test_trace_is_created_once_then_generations_attach(self):
        trace = {"id": "t1", "opened": False, "name": "process_document", "ref_id": "app-1", "metadata": {}}
        tokens = SimpleNamespace(prompt_tokens=120, completion_tokens=30)
        first = tracing.generation_events(trace, "classify", "gpt-6-luna", "prompt", "{}", tokens, 0.0001, "s", "e")
        second = tracing.generation_events(trace, "extract_payslip", "gpt-6.1-terra", "prompt", "{}", tokens, 0.002, "s", "e", error="503")
        self.assertEqual([e["type"] for e in first + second], ["trace-create", "generation-create", "generation-create"])
        self.assertEqual((second[0]["body"]["traceId"], second[0]["body"]["level"], second[0]["body"]["usage"]["input"]), ("t1", "ERROR", 120))

    def test_long_prompts_are_clipped(self):
        self.assertLess(len(tracing.clip("x" * 50_000)), 4_100)

    def test_without_keys_tracing_does_nothing(self):
        with patch.object(tracing, "LANGFUSE_PUBLIC_KEY", ""):
            tracing.start("process_document", "app-1")
            tracing.generation("classify", "gpt-6-luna", "p", "o", None, 0, "s")  # no running loop needed: returns early


if __name__ == "__main__":
    unittest.main()
