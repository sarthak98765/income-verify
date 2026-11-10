import asyncio
from typing import Awaitable, Callable, List
from openai import AsyncOpenAI
from config import *
from logger import custom_logger
from utils import JSON_RULES, TUNABLE, extract_json, rejected_param, user_content
import tracing
import usage

UNSUPPORTED: dict[str, set[str]] = {}

class TruncatedResponse(RuntimeError):
    """The model hit the output limit. Retrying is pointless — send less input."""

def build_request(model, system_prompt, user_prompt, temp, json_mode, drop, images=()):
    request = {"model": model, "messages": [{"role": "system", "content": system_prompt + JSON_RULES if json_mode else system_prompt}, {"role": "user", "content": user_content(user_prompt, list(images))}]}
    if "max_completion_tokens" not in drop:
        request["max_completion_tokens"] = MAX_OUTPUT_TOKENS
    if "temperature" not in drop:
        request["temperature"] = temp
    if json_mode and "response_format" not in drop:
        request["response_format"] = {"type": "json_object"}
    if model in REASONING_EFFORT and "reasoning_effort" not in drop:
        request["reasoning_effort"] = REASONING_EFFORT[model]
    return request

async def call_model(model, system_prompt, user_prompt, temp, json_mode, images, name="llm"):
    """One request; a parameter the model rejects is dropped (remembered per model) and the request sent again.
    Every call, failed or not, is traced (when tracing is on)."""
    client = AsyncOpenAI(api_key=OPENAI_API_KEY, timeout=LLM_TIMEOUT, max_retries=0)
    drop = UNSUPPORTED.setdefault(model, set())
    started, response, content = tracing.now(), None, None
    try:
        for _ in range(len(TUNABLE) + 1):
            try:
                response = await client.chat.completions.create(**build_request(model, system_prompt, user_prompt, temp, json_mode, drop, images))
                break
            except Exception as error:
                param = rejected_param(error)
                if not param or param in drop:
                    raise
                drop.add(param)
                custom_logger.warning(f"ai | {model} rejected '{param}' — retrying without it")
        else:
            raise RuntimeError(f"{model} rejected every parameter combination")
        choice = response.choices[0]
        content = (choice.message.content or "").strip()
        usage.add_llm(model, response.usage)
        custom_logger.info(f"ai | model={model} tokens={getattr(response.usage, 'total_tokens', 'N/A')} {f'images={len(images)} ' if images else ''}finish={choice.finish_reason}")
        if choice.finish_reason == "length":
            raise TruncatedResponse(f"{model} response truncated — send less input")
        if not content:
            raise RuntimeError(f"{model} returned an empty response")
        tracing.generation(name, model, user_prompt, content, response.usage, usage.cost_of(model, response.usage), started)
        return extract_json(content) if json_mode else content
    except Exception as error:
        tracing.generation(name, model, user_prompt, content, getattr(response, "usage", None), usage.cost_of(model, getattr(response, "usage", None)), started, error=str(error) or type(error).__name__)
        raise
    finally:
        await client.close()

async def with_retries(model, system_prompt, user_prompt, temp, json_mode, images, name):
    """Transient failures back off and retry; truncation is raised at once (the caller sends less)."""
    last_error: Exception = RuntimeError("unknown error")
    for attempt in range(1, LLM_RETRY_ATTEMPTS + 1):
        try:
            return await call_model(model, system_prompt, user_prompt, temp, json_mode, images, name)
        except TruncatedResponse:
            raise
        except Exception as error:
            last_error = error
            if attempt == LLM_RETRY_ATTEMPTS:
                custom_logger.error(f"ai | {model}: all {LLM_RETRY_ATTEMPTS} attempts failed: {error}")
                break
            wait = LLM_BACKOFF_BASE ** attempt
            custom_logger.warning(f"ai | {model} attempt {attempt} failed: {error} — retrying in {wait}s")
            await asyncio.sleep(wait)
    raise last_error

async def get_ai_output(system_prompt, user_prompt, model, temp=0, json_mode=False, images=(), name="llm"):
    """The one place any LLM is called. Retries on the model; if it still fails, one more round on its fallback
    model (FALLBACK_MODELS), counted in the task's usage. `name` labels the call in traces."""
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not set")
    try:
        return await with_retries(model, system_prompt, user_prompt, temp, json_mode, list(images), name)
    except TruncatedResponse:
        raise
    except Exception as error:
        fallback = FALLBACK_MODELS.get(model)
        if not fallback:
            raise
        custom_logger.warning(f"ai | {model} failed ({error}) — falling back to {fallback} for {name}")
        usage.add_fallback()
        return await with_retries(fallback, system_prompt, user_prompt, temp, json_mode, list(images), f"{name} (fallback)")

async def halving(items: List, call: Callable[[List, int], Awaitable[List]], start: int = 0) -> List:
    """`call(items, start)` for the whole list in one request; on truncation, split in half and ask each half again."""
    try:
        return await call(items, start)
    except TruncatedResponse:
        if len(items) == 1:
            raise
        mid = len(items) // 2
        custom_logger.warning(f"ai | truncated on {len(items)} item(s) — splitting into {mid}+{len(items) - mid}")
        return await halving(items[:mid], call, start) + await halving(items[mid:], call, start + mid)
