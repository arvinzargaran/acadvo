import json
import logging
import time
import uuid

from groq import RateLimitError as GroqRateLimitError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.client import get_groq_client, record_ai_success, record_ai_failure
from app.ai.context import build_system_prompt
from app.ai.tools import get_groq_tools
from app.ai.tool_executor import execute_tool
from app.config import settings
from app.models.conversation import Conversation
from app.models.message import Message, MessageRole

logger = logging.getLogger("acadvo.ai")

MAX_TOOL_ROUNDS = 10
MAX_HISTORY_MESSAGES = 50


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
        """
        nonlocal total_prompt_tokens, total_completion_tokens
        call_start = time.perf_counter()
        try:
            resp = client.chat.completions.create(
                model=settings.GROQ_MODEL,
                messages=messages,
                tools=tools,
                tool_choice="auto",
            )
            record_ai_success()
        except GroqRateLimitError:
            logger.warning("groq rate limited", extra={"ai_round": round_no})
            raise
        except Exception:
            record_ai_failure()
            logger.exception("groq call failed", extra={"ai_round": round_no})
            raise

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

    def _summary_extra(outcome: str) -> dict:
        return {
            "ai_rounds": rounds,
            "tool_calls": len(all_tool_calls),
            "duration_ms": round((time.perf_counter() - loop_start) * 1000, 1),
            "prompt_tokens": total_prompt_tokens or None,
            "completion_tokens": total_completion_tokens or None,
            "outcome": outcome,
        }

    response = _model_call(0)

    for round_idx in range(MAX_TOOL_ROUNDS):
        assistant_message = response.choices[0].message
        tool_calls = assistant_message.tool_calls

        if not tool_calls:
            # Final text response
            assistant_text = assistant_message.content or ""

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

        response = _model_call(round_idx + 1)

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
