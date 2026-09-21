import json
import logging
import random
import re
import time
import uuid

from groq import (
    APIConnectionError as GroqAPIConnectionError,
    APIStatusError as GroqAPIStatusError,
    APITimeoutError as GroqAPITimeoutError,
    InternalServerError as GroqInternalServerError,
    RateLimitError as GroqRateLimitError,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.client import (
    AIUnavailableError,
    clean_model_text,
    get_groq_client,
    record_ai_success,
    record_ai_failure,
    run_blocking,
)
from app.ai.context import build_system_prompt
from app.ai.tools import get_groq_tools
from app.ai.tool_executor import execute_tool
from app.config import settings
from app.models.conversation import Conversation
from app.models.message import Message, MessageRole

logger = logging.getLogger("acadvo.ai")

MAX_TOOL_ROUNDS = 10
MAX_HISTORY_MESSAGES = 50

# Retry policy for transient Groq failures (5xx / connection / timeout / rate
# limit). Up to 3 attempts with exponential backoff + small jitter.
AI_MAX_ATTEMPTS = 3
AI_BACKOFF_BASE = 0.5  # seconds; delays ~0.5s, 1.0s, 2.0s
AI_BACKOFF_JITTER = 0.25  # seconds; added uniformly on top of each delay
# Ceiling on honouring a provider-stated retry delay. Groq's free tier answers a
# rate-limited call with the exact number of seconds until the window reopens,
# and that number is routinely ~20s — far longer than any exponential backoff
# starting at half a second. Waiting it out is the difference between the tool
# loop working and failing every time; the cap stops a pathological value from
# holding a request open indefinitely.
AI_MAX_PROVIDER_DELAY = 30.0


def _is_transient_groq_error(exc: Exception) -> bool:
    """Return True for retryable Groq failures.

    Transient: connection errors, timeouts, 5xx server errors, and rate limits.
    Non-transient 4xx (bad request / auth / not found) are NOT retried.
    """
    if isinstance(
        exc,
        (
            GroqAPIConnectionError,  # includes GroqAPITimeoutError
            GroqAPITimeoutError,
            GroqInternalServerError,
            GroqRateLimitError,
        ),
    ):
        return True
    if isinstance(exc, GroqAPIStatusError):
        status = getattr(exc, "status_code", None)
        return status is not None and status >= 500
    return False


_RETRY_AFTER_RE = re.compile(r"try again in ([0-9]+(?:\.[0-9]+)?)\s*s", re.IGNORECASE)


def _provider_retry_delay(exc: Exception) -> float | None:
    """Seconds the provider asked us to wait, if it said.

    Groq returns this two ways: a Retry-After header, and a sentence in the
    error body. The header is preferred; the body is parsed because the SDK
    does not always surface headers on the exception.
    """
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None)
    if headers:
        raw = headers.get("retry-after") or headers.get("Retry-After")
        if raw:
            try:
                return float(raw)
            except (TypeError, ValueError):
                pass
    match = _RETRY_AFTER_RE.search(str(exc))
    if match:
        return float(match.group(1))
    return None


def _error_detail(exc: Exception) -> dict:
    """Describe a Groq failure well enough to act on it.

    "transient failure" on its own cannot be diagnosed: a 429 for too many
    requests, a 429 for one request larger than the whole per-minute allowance,
    a 500 and a dropped connection all read identically, and they call for
    completely different responses — wait, shrink the request, retry, check the
    network. The message is the provider's own and carries no user content.
    """
    detail = {"error_type": type(exc).__name__}
    status = getattr(exc, "status_code", None)
    if status is not None:
        detail["status_code"] = status
    message = str(exc)
    if message:
        detail["error_message"] = message[:300]
    return detail


def _extract_usage(response) -> dict | None:
    """Pull token usage off a Groq response if it exposes any."""
    usage = getattr(response, "usage", None)
    if not usage:
        return None
    return {
        "prompt_tokens": getattr(usage, "prompt_tokens", None),
        "completion_tokens": getattr(usage, "completion_tokens", None),
        "total_tokens": getattr(usage, "total_tokens", None),
    }


async def send_message(
    conversation_id: uuid.UUID,
    user_message: str,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> dict:
    """
    Process a user message: save it, build context, call Groq with tools,
    execute any tool calls in a loop, return the final assistant response.
    """
    result = await db.execute(
        select(Conversation)
        .where(Conversation.id == conversation_id, Conversation.user_id == user_id)
        .options(selectinload(Conversation.messages))
    )
    conversation = result.scalar_one_or_none()
    if not conversation:
        raise ValueError("Conversation not found")

    user_msg = Message(
        conversation_id=conversation_id,
        role=MessageRole.user,
        content=user_message,
    )
    db.add(user_msg)
    await db.commit()

    system_prompt = await build_system_prompt(user_id, db)
    client = get_groq_client()

    # Build message list
    messages = [{"role": "system", "content": system_prompt}]
    recent_messages = conversation.messages[-MAX_HISTORY_MESSAGES:]
    for msg in recent_messages:
        role = "user" if msg.role == MessageRole.user else "assistant"
        messages.append({"role": role, "content": msg.content})
    messages.append({"role": "user", "content": user_message})

    tools = get_groq_tools()
    all_tool_calls = []

    loop_start = time.perf_counter()
    rounds = 0
    total_prompt_tokens = 0
    total_completion_tokens = 0

    def _model_call(round_no: int):
        """Call Groq once, timing it and logging latency + token usage.

        No message content is logged — only latency and token counts.

        Synchronous on purpose: it wraps the blocking Groq SDK and its retry
        sleeps. Always invoke it through ``_model_call_async`` so the whole
        thing — request plus backoff — happens off the event loop.
        """
        nonlocal total_prompt_tokens, total_completion_tokens
        call_start = time.perf_counter()
        resp = None
        for attempt in range(AI_MAX_ATTEMPTS):
            try:
                resp = client.chat.completions.create(
                    model=settings.GROQ_MODEL,
                    messages=messages,
                    tools=tools,
                    tool_choice="auto",
                )
                record_ai_success()
                break
            except Exception as exc:
                if not _is_transient_groq_error(exc):
                    # Non-transient (4xx bad request / auth) — fail fast.
                    record_ai_failure()
                    logger.exception("groq call failed", extra={"ai_round": round_no})
                    raise

                if attempt + 1 >= AI_MAX_ATTEMPTS:
                    # Exhausted retries on a transient error — trip the circuit
                    # breaker and surface a graceful "AI unavailable" signal
                    # (router maps AIUnavailableError -> 503) instead of a 500.
                    record_ai_failure()
                    logger.warning(
                        "groq transient failure, retries exhausted",
                        extra={
                            "ai_round": round_no,
                            "attempts": attempt + 1,
                            **_error_detail(exc),
                        },
                    )
                    raise AIUnavailableError() from exc

                delay = AI_BACKOFF_BASE * (2 ** attempt) + random.uniform(
                    0, AI_BACKOFF_JITTER
                )
                # A rate limit is not a blip to back off from — it is a stated
                # wait. Exponential backoff from 0.5s burns all three attempts
                # in two seconds against a window that reopens in twenty, which
                # is why a tool call followed by its answer never completed on
                # the free tier: two rounds do not fit in one minute's budget.
                stated = _provider_retry_delay(exc)
                if stated is not None:
                    delay = min(max(stated + 0.5, delay), AI_MAX_PROVIDER_DELAY)
                logger.warning(
                    "groq transient failure, retrying",
                    extra={
                        "ai_round": round_no,
                        "attempt": attempt + 1,
                        "retry_in_ms": round(delay * 1000, 1),
                        **_error_detail(exc),
                    },
                )
                time.sleep(delay)

        duration_ms = round((time.perf_counter() - call_start) * 1000, 1)
        extra = {"ai_round": round_no, "duration_ms": duration_ms}
        usage = _extract_usage(resp)
        if usage:
            extra.update(usage)
            if usage["prompt_tokens"]:
                total_prompt_tokens += usage["prompt_tokens"]
            if usage["completion_tokens"]:
                total_completion_tokens += usage["completion_tokens"]
        logger.debug("groq call complete", extra=extra)
        return resp

    async def _model_call_async(round_no: int):
        """Run one _model_call in a worker thread.

        A single chat turn can make MAX_TOOL_ROUNDS model calls, each with up to
        AI_MAX_ATTEMPTS retries and exponential-backoff sleeps. Run inline, that
        is tens of seconds during which this uvicorn worker serves nobody.
        """
        return await run_blocking(_model_call, round_no)

    def _summary_extra(outcome: str) -> dict:
        return {
            "ai_rounds": rounds,
            "tool_calls": len(all_tool_calls),
            "duration_ms": round((time.perf_counter() - loop_start) * 1000, 1),
            "prompt_tokens": total_prompt_tokens or None,
            "completion_tokens": total_completion_tokens or None,
            "outcome": outcome,
        }

    response = await _model_call_async(0)

    for round_idx in range(MAX_TOOL_ROUNDS):
        assistant_message = response.choices[0].message
        tool_calls = assistant_message.tool_calls

        if not tool_calls:
            # Final text response
            # Shown to the user verbatim: strip a reasoning block if the model
            # emitted one inline, but never touch fenced code they asked for.
            assistant_text = clean_model_text(assistant_message.content, strip_fence=False)

            assistant_msg = Message(
                conversation_id=conversation_id,
                role=MessageRole.assistant,
                content=assistant_text,
                tool_calls=all_tool_calls if all_tool_calls else None,
            )
            db.add(assistant_msg)

            if not conversation.title and len(conversation.messages) <= 1:
                conversation.title = user_message[:100]

            await db.commit()
            logger.info("ai message handled", extra=_summary_extra("completed"))
            return {"message": assistant_text, "tool_calls": all_tool_calls}

        rounds += 1

        # Append the assistant message with tool calls to history
        messages.append({
            "role": "assistant",
            "content": assistant_message.content,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in tool_calls
            ],
        })

        # Execute each tool and append results
        for tc in tool_calls:
            tool_name = tc.function.name
            try:
                tool_args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                tool_args = {}

            tool_result = await execute_tool(
                tool_name=tool_name,
                tool_input=tool_args,
                user_id=user_id,
                conversation_id=conversation_id,
                db=db,
            )

            all_tool_calls.append({
                "tool": tool_name,
                "input": tool_args,
                "result": json.loads(tool_result),
            })

            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": tool_result,
            })

        response = await _model_call_async(round_idx + 1)

    # Hit max rounds
    logger.info("ai message handled", extra=_summary_extra("max_rounds"))
    assistant_msg = Message(
        conversation_id=conversation_id,
        role=MessageRole.assistant,
        content="I've completed several actions but reached the limit for this response. Please send another message to continue.",
        tool_calls=all_tool_calls if all_tool_calls else None,
    )
    db.add(assistant_msg)
    await db.commit()

    return {"message": assistant_msg.content, "tool_calls": all_tool_calls}


async def create_conversation(
    user_id: uuid.UUID,
    db: AsyncSession,
    is_onboarding: bool = False,
    title: str | None = None,
) -> Conversation:
    conversation = Conversation(
        user_id=user_id,
        title=title,
        is_onboarding=is_onboarding,
    )
    db.add(conversation)
    await db.commit()
    await db.refresh(conversation)
    return conversation
