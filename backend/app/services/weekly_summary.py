import json
from datetime import datetime, timedelta, timezone

from app.ai.client import get_groq_client
from app.config import settings
from app.services.degree import get_degree_summary, list_courses
from app.services.career import list_career_targets, list_timeline_events

_SUMMARY_PROMPT = """You are an experienced academic advisor writing a short weekly check-in note for this student.

Student profile:
- University: {university}
- Program: {program}
- Career target: {career_target}
- Graduation: {graduation_year}

Current data:
- Degree progress: {degree_progress}% complete, {credits_completed}/{credits_total} credits
- Courses in progress: {in_progress_courses}
- Career targets: {career_targets}
- Upcoming deadlines: {deadlines}

Return JSON:
{{
  "greeting": "<one plain sentence naming what this week looks like for them>",
  "highlights": ["<concrete fact from their data worth noting>", "<another concrete fact>"],
  "action_items": ["<specific action 1>", "<specific action 2>", "<specific action 3>"],
  "motivation": "<one short, matter-of-fact closing line>"
}}

Tone rules — follow strictly:
- Write like a calm, seasoned advisor, not a cheerleader. No exclamation marks.
- No filler like "I'm excited", "let's work together", "you've got this", "journey", or "crush it".
- Every sentence must reference their actual data or name a concrete next step. If there is little data, say so plainly and suggest the single most useful first step.
- Keep each item under 20 words."""


CACHE_TTL = timedelta(hours=24)


async def generate_weekly_summary(user, db, force_refresh: bool = False) -> dict:
    # Serve the cached summary unless it's stale or a refresh is requested —
    # this endpoint is hit on every dashboard load and each miss costs an LLM call.
    if (
        not force_refresh
        and user.weekly_summary is not None
        and user.weekly_summary_generated_at is not None
        and datetime.now(timezone.utc) - user.weekly_summary_generated_at < CACHE_TTL
    ):
        return user.weekly_summary

    client = get_groq_client()

    summary = await get_degree_summary(user.id, db)
    courses = await list_courses(user.id, db)
    targets = await list_career_targets(user.id, db)
    events = await list_timeline_events(user.id, db)

    in_progress = [f"{c.course_code} ({c.course_name})" for c in courses if c.status == "in_progress"]
    target_list = [f"{t.company_name} - {t.role_type or 'TBD'} ({t.status})" for t in targets[:5]]
    upcoming = [f"{e.title} ({e.event_date})" for e in sorted(events, key=lambda e: e.event_date)[:5]]

    prompt = _SUMMARY_PROMPT.format(
        university=user.university or "Unknown",
        program=user.program or "Unknown",
        career_target=user.career_target or "Software Engineering",
        graduation_year=user.expected_graduation_year or "Unknown",
        degree_progress=summary.get("overall_percentage", 0),
        credits_completed=summary.get("total_credits_completed", 0),
        credits_total=summary.get("total_credits_required", 0),
        in_progress_courses=", ".join(in_progress) if in_progress else "None",
        career_targets=", ".join(target_list) if target_list else "None set",
        deadlines=", ".join(upcoming) if upcoming else "None upcoming",
    )

    response = client.chat.completions.create(
        model=settings.GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1024,
    )
    text = response.choices[0].message.content.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        result = {"greeting": "Your weekly check-in.", "highlights": [], "action_items": [text], "motivation": "Review the items above when you have a moment."}

    user.weekly_summary = result
    user.weekly_summary_generated_at = datetime.now(timezone.utc)
    db.add(user)
    await db.commit()
    return result
