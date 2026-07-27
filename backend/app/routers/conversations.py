import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select

logger = logging.getLogger(__name__)
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.limiter import limiter
from app.models.user import User
from app.models.conversation import Conversation
from app.models.message import Message
from app.schemas.conversation import (
    AIResponse,
    ConversationCreate,
    ConversationDetailResponse,
    ConversationResponse,
    MessageCreate,
)
from app.ai.client import AIDisabledError, AIUnavailableError
from app.ai.conversation import create_conversation, send_message

router = APIRouter()


@router.post("", response_model=ConversationResponse)
@limiter.limit("20/hour")
async def start_conversation(
    request: Request,
    data: ConversationCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conversation = await create_conversation(
        user_id=user.id,
        db=db,
        is_onboarding=data.is_onboarding,
        title=data.title,
    )
    return conversation


@router.get("", response_model=list[ConversationResponse])
async def list_conversations(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == user.id)
        .order_by(Conversation.updated_at.desc())
    )
    return result.scalars().all()


@router.get("/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation(
    conversation_id: uuid.UUID,
    limit: int = Query(default=100, ge=1, le=500),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conv_result = await db.execute(
        select(Conversation)
        .where(Conversation.id == conversation_id, Conversation.user_id == user.id)
    )
    conversation = conv_result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    msg_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(Message.created_at.asc())
        .limit(limit)
    )
    messages = msg_result.scalars().all()

    return ConversationDetailResponse(
        id=conversation.id,
        user_id=conversation.user_id,
        title=conversation.title,
        is_onboarding=conversation.is_onboarding,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        messages=list(messages),
    )


@router.delete("/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Conversation)
        .where(Conversation.id == conversation_id, Conversation.user_id == user.id)
    )
    conversation = result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    await db.delete(conversation)
    await db.commit()


@router.post("/{conversation_id}/messages", response_model=AIResponse)
@limiter.limit("60/hour")
async def post_message(
    request: Request,
    conversation_id: uuid.UUID,
    data: MessageCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await send_message(
            conversation_id=conversation_id,
            user_message=data.content,
            user_id=user.id,
            db=db,
        )
        return AIResponse(message=result["message"], tool_calls=result["tool_calls"])
    except (AIDisabledError, AIUnavailableError) as e:
        raise HTTPException(status_code=503, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        logger.exception("Unhandled error in post_message")
        raise HTTPException(status_code=500, detail="An unexpected error occurred")
