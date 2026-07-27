"""Tests for AI tool executor: degree summary, unknown tool, flag_risk."""

import json
import uuid

import pytest

from app.ai.tool_executor import execute_tool


# ── Degree Summary via Tool ──────────────────────────────────────────

async def test_execute_tool_degree_summary(db, test_user):
    result_str = await execute_tool(
        tool_name="get_degree_summary",
        tool_input={},
        user_id=test_user.id,
        conversation_id=None,
        db=db,
    )
    result = json.loads(result_str)
    assert "buckets" in result
    assert "total_credits_required" in result
    assert "overall_percentage" in result


# ── Unknown Tool ─────────────────────────────────────────────────────

async def test_execute_tool_unknown(db, test_user):
    result_str = await execute_tool(
        tool_name="nonexistent_tool",
        tool_input={},
        user_id=test_user.id,
        conversation_id=None,
        db=db,
    )
    result = json.loads(result_str)
    assert "error" in result
    assert "Unknown tool" in result["error"]


# ── Flag Risk ────────────────────────────────────────────────────────

async def test_execute_tool_flag_risk(db, test_user):
    result_str = await execute_tool(
        tool_name="flag_risk",
        tool_input={
            "description": "GPA dropping below 3.0 threshold",
            "severity": "high",
        },
        user_id=test_user.id,
        conversation_id=None,
        db=db,
    )
    result = json.loads(result_str)
    assert result["success"] is True
    assert "Risk flagged" in result["message"]
