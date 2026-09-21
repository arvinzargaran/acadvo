"""Seed a fully populated demo account.

Why this exists: a visitor who lands on a signup form sees nothing. The app is
only legible once there is a degree behind it — courses with grades across real
terms, requirement buckets partly filled, projects mid-flight, a career pipeline
with something in every column. This builds that account so a reader can see the
product instead of an empty shell.

Everything here is fabricated. There is no real student, no real transcript, and
no real employer relationship: the companies are placeholders and the person does
not exist. That is the point. A demo backed by synthetic data can be deployed
publicly, and the worst case for a breach is that somebody learns what a
made-up student's made-up grades were.

Run it:

    DATABASE_URL=postgresql+asyncpg://acadvo:acadvo@localhost:5432/acadvo \\
    JWT_SECRET_KEY=... DEBUG=True \\
    python -m app.scripts.seed_demo

Re-running replaces the demo account's data and touches nothing else.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import delete, select

from app.config import settings
from app.database import async_session
from app.models.career import CareerStatus, CareerTarget, TimelineCategory, TimelineEvent
from app.models.degree import Course, CourseStatus, DegreeRequirement
from app.models.project import Milestone, MilestoneStatus, Project, ProjectStatus
from app.models.user import User
from app.services.auth import hash_password

DEMO_EMAIL = "demo@acadvo.app"
DEMO_PASSWORD = "DemoStudent2026!"
DEMO_NAME = "Alex Morgan"
SEED_UNIVERSITY = "York University"

# (bucket, credits required, description)
REQUIREMENTS = [
    ("Major Core", 45.00, "Required EECS courses for the BSc Computer Science major."),
    ("Major Electives", 18.00, "Upper-year EECS electives, at least 12.00 at the 4000 level."),
    ("Mathematics", 12.00, "Calculus, linear algebra and discrete mathematics."),
    ("General Education", 12.00, "Humanities and social science breadth requirement."),
    ("Free Electives", 9.00, "Any faculty, any level."),
]

# (code, name, credits, status, term, grade, bucket)
COURSES = [
    ("EECS 1012", "Net-Centric Introduction to Computer Science", 3.00, "completed", "Fall 2023", "A", "Major Core"),
    ("EECS 1015", "Introduction to Computer Science I", 3.00, "completed", "Fall 2023", "A+", "Major Core"),
    ("MATH 1013", "Applied Calculus I", 3.00, "completed", "Fall 2023", "B+", "Mathematics"),
    ("HUMA 1105", "Myth and Imagination", 3.00, "completed", "Fall 2023", "B+", "General Education"),
    ("EECS 1021", "Object Oriented Programming", 3.00, "completed", "Winter 2024", "A", "Major Core"),
    ("EECS 1022", "Programming for Mobile Computing", 3.00, "completed", "Winter 2024", "A", "Major Core"),
    ("MATH 1014", "Applied Calculus II", 3.00, "completed", "Winter 2024", "B", "Mathematics"),
    ("MATH 1090", "Introduction to Logic for Computer Science", 3.00, "completed", "Winter 2024", "B+", "Mathematics"),
    ("EECS 2001", "Introduction to the Theory of Computation", 3.00, "completed", "Fall 2024", "B+", "Major Core"),
    ("EECS 2011", "Fundamentals of Data Structures", 3.00, "completed", "Fall 2024", "A", "Major Core"),
    ("EECS 2030", "Advanced Object Oriented Programming", 3.00, "completed", "Fall 2024", "A", "Major Core"),
    ("MATH 2030", "Elementary Probability", 3.00, "completed", "Fall 2024", "B", "Mathematics"),
    ("EECS 2021", "Computer Organization", 3.00, "completed", "Winter 2025", "B+", "Major Core"),
    ("EECS 2200", "Electrical Circuits and Signals", 3.00, "completed", "Winter 2025", "B", "Major Electives"),
    ("EECS 3101", "Design and Analysis of Algorithms", 3.00, "completed", "Winter 2025", "A", "Major Core"),
    ("SOSC 1140", "Self, Culture and Society", 3.00, "completed", "Winter 2025", "A", "General Education"),
    ("EECS 3201", "Digital Logic Design", 3.00, "completed", "Fall 2025", "B+", "Major Electives"),
    ("EECS 3213", "Communication Networks", 3.00, "completed", "Fall 2025", "B+", "Major Electives"),
    ("EECS 3221", "Operating System Fundamentals", 3.00, "completed", "Fall 2025", "A", "Major Core"),
    ("EECS 3311", "Software Design", 3.00, "completed", "Fall 2025", "A+", "Major Core"),
    ("EECS 3421", "Introduction to Database Systems", 3.00, "in_progress", "Winter 2026", None, "Major Core"),
    ("EECS 3482", "Introduction to Computer Security", 3.00, "in_progress", "Winter 2026", None, "Major Electives"),
    ("EECS 4413", "Building E-Commerce Systems", 3.00, "in_progress", "Winter 2026", None, "Major Electives"),
    ("ECON 1000", "Introduction to Microeconomics", 3.00, "in_progress", "Winter 2026", None, "Free Electives"),
    ("EECS 4441", "Human-Computer Interaction", 3.00, "planned", "Fall 2026", None, "Major Electives"),
    ("EECS 4461", "Digital Media and Agents", 3.00, "planned", "Fall 2026", None, "Major Electives"),
    ("EECS 4471", "Virtual and Augmented Reality", 3.00, "planned", "Fall 2026", None, "Major Electives"),
    ("HUMA 2820", "Culture and Technology", 3.00, "planned", "Fall 2026", None, "General Education"),
    ("EECS 4080", "Computer Science Project", 3.00, "planned", "Winter 2027", None, "Major Core"),
    ("EECS 4312", "Software Engineering Requirements", 3.00, "planned", "Winter 2027", None, "Major Core"),
    ("GEOG 2000", "Cities and Urban Life", 3.00, "planned", "Winter 2027", None, "Free Electives"),
]

PROJECTS = [
    {
        "name": "Transit Delay Predictor",
        "description": "Predicts streetcar bunching from open TTC vehicle feeds and surfaces it as a live map.",
        "priority": 1,
        "status": ProjectStatus.deployed,
        "tech_stack": "Python, FastAPI, PostgreSQL, scikit-learn, React",
        "repo_url": "https://github.com/example/transit-delay-predictor",
        "product_framing": "Riders decide whether to wait or walk. The useful output is a number of minutes, not a model score.",
        "milestones": [
            ("Ingest the vehicle feed", MilestoneStatus.complete, -120),
            ("Baseline headway model", MilestoneStatus.complete, -80),
            ("Live map front end", MilestoneStatus.complete, -40),
            ("Write up the evaluation", MilestoneStatus.in_progress, 21),
        ],
    },
    {
        "name": "Course Prerequisite Graph",
        "description": "Parses a university calendar into a dependency graph and finds the shortest path to any course.",
        "priority": 2,
        "status": ProjectStatus.in_progress,
        "tech_stack": "TypeScript, D3, Node, SQLite",
        "repo_url": "https://github.com/example/prereq-graph",
        "product_framing": "Advising answers 'can I take this yet' slowly. The graph answers it instantly.",
        "milestones": [
            ("Calendar parser", MilestoneStatus.complete, -45),
            ("Cycle detection on the graph", MilestoneStatus.in_progress, 10),
            ("Interactive layout", MilestoneStatus.pending, 35),
        ],
    },
    {
        "name": "Study Session Tracker",
        "description": "A small CLI that logs focused study time and reports weekly consistency.",
        "priority": 3,
        "status": ProjectStatus.interview_ready,
        "tech_stack": "Go, SQLite",
        "repo_url": "https://github.com/example/study-tracker",
        "product_framing": "Consistency is the metric that matters; total hours flatter you and predict nothing.",
        "milestones": [
            ("Session logging", MilestoneStatus.complete, -200),
            ("Weekly report", MilestoneStatus.complete, -180),
        ],
    },
]

CAREER_TARGETS = [
    ("Northwind Systems", "Backend Engineering Intern", "Toronto, ON", CareerStatus.offer, "Summer 2026"),
    ("Aperture Labs", "Software Engineering Intern", "Remote", CareerStatus.interviewing, "Summer 2026"),
    ("Meridian Health", "Platform Intern", "Toronto, ON", CareerStatus.interviewing, "Summer 2026"),
    ("Blue Harbour Analytics", "Data Engineering Intern", "Vancouver, BC", CareerStatus.applied, "Summer 2026"),
    ("Cedar Financial", "Developer Intern", "Toronto, ON", CareerStatus.applied, "Summer 2026"),
    ("Lantern Robotics", "Embedded Software Intern", "Waterloo, ON", CareerStatus.researching, "Fall 2026"),
    ("Quarry Interactive", "Gameplay Engineering Intern", "Montreal, QC", CareerStatus.rejected, "Summer 2026"),
]

TIMELINE = [
    ("Northwind offer decision due", TimelineCategory.deadline, 9, True),
    ("Aperture Labs final round", TimelineCategory.milestone, 4, True),
    ("EECS 3421 project demo", TimelineCategory.academic, 16, True),
    ("Winter term ends", TimelineCategory.academic, 38, False),
    ("Fall 2026 enrolment opens", TimelineCategory.academic, 66, False),
    ("Publish the transit write-up", TimelineCategory.goal, 21, False),
    ("Summer internship starts", TimelineCategory.co_op, 118, False),
]


async def seed() -> None:
    today = date.today()
    now = datetime.now(timezone.utc)

    async with async_session() as db:
        existing = (await db.execute(select(User).where(User.email == DEMO_EMAIL))).scalar_one_or_none()

        if existing is None:
            user = User(email=DEMO_EMAIL, hashed_password=hash_password(DEMO_PASSWORD), full_name=DEMO_NAME)
            db.add(user)
            await db.flush()
            print(f"created {DEMO_EMAIL}")
        else:
            user = existing
            # Replace only this account's rows. Every delete is scoped by
            # user_id, so a populated database belonging to somebody else is
            # untouched even if this is pointed at one by mistake.
            await db.execute(delete(Milestone).where(Milestone.project_id.in_(
                select(Project.id).where(Project.user_id == user.id)
            )))
            for model in (Course, DegreeRequirement, Project, CareerTarget, TimelineEvent):
                await db.execute(delete(model).where(model.user_id == user.id))
            user.hashed_password = hash_password(DEMO_PASSWORD)
            print(f"reset {DEMO_EMAIL}")

        user.full_name = DEMO_NAME
        user.university = SEED_UNIVERSITY
        user.program = "Computer Science"
        user.start_year = 2023
        user.expected_graduation_year = 2027
        user.country = "Canada"
        user.city = "Toronto"
        user.career_target = "Backend or platform engineering internship for Summer 2026"
        user.onboarding_complete = True
        user.email_verified = True
        user.terms_accepted_at = now
        user.terms_version = "2026-08-01"
        user.study_streak = 12
        user.longest_study_streak = 23
        user.last_study_date = today
        user.daily_study_goal_minutes = 45

        buckets: dict[str, DegreeRequirement] = {}
        for name, credits, description in REQUIREMENTS:
            bucket = DegreeRequirement(
                user_id=user.id, bucket_name=name, credits_required=credits, description=description
            )
            db.add(bucket)
            buckets[name] = bucket
        await db.flush()

        for code, name, credits, status, term, grade, bucket_name in COURSES:
            db.add(Course(
                user_id=user.id,
                course_code=code,
                course_name=name,
                credit_value=credits,
                status=CourseStatus(status),
                term=term,
                grade=grade,
                requirement_bucket_id=buckets[bucket_name].id,
            ))

        for spec in PROJECTS:
            project = Project(
                user_id=user.id,
                name=spec["name"],
                description=spec["description"],
                priority=spec["priority"],
                status=spec["status"],
                tech_stack=spec["tech_stack"],
                repo_url=spec["repo_url"],
                product_framing=spec["product_framing"],
            )
            db.add(project)
            await db.flush()
            for index, (title, status, offset) in enumerate(spec["milestones"]):
                db.add(Milestone(
                    project_id=project.id,
                    title=title,
                    status=status,
                    target_date=today + timedelta(days=offset),
                    completed_at=now if status is MilestoneStatus.complete else None,
                    order_index=index,
                ))

        for company, role, location, status, term in CAREER_TARGETS:
            db.add(CareerTarget(
                user_id=user.id,
                company_name=company,
                role_type=role,
                location=location,
                status=status,
                target_term=term,
            ))

        for title, category, offset, hard in TIMELINE:
            db.add(TimelineEvent(
                user_id=user.id,
                title=title,
                event_date=today + timedelta(days=offset),
                category=category,
                is_hard_deadline=hard,
            ))

        await db.commit()

    completed = sum(1 for c in COURSES if c[3] == "completed")
    print(
        f"seeded {len(COURSES)} courses ({completed} completed), {len(REQUIREMENTS)} requirement buckets, "
        f"{len(PROJECTS)} projects, {len(CAREER_TARGETS)} career targets, {len(TIMELINE)} timeline events"
    )
    print(f"\nsign in with  {DEMO_EMAIL}  /  {DEMO_PASSWORD}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--allow-production",
        action="store_true",
        help="Run even with DEBUG off. Needed only for a deliberately seeded public demo.",
    )
    args = parser.parse_args()

    # The account has a published password. Creating it on a deployment serving
    # real students would hand anybody an account on their instance, so it takes
    # an explicit flag rather than happening because an env var was inherited.
    if not settings.DEBUG and not args.allow_production:
        print(
            "Refusing to seed: DEBUG is off, so this looks like a real deployment.\n"
            "The demo account's password is published in this file. Pass --allow-production\n"
            "only if this instance exists to be a public demo.",
            file=sys.stderr,
        )
        return 1

    print(f"database: {os.environ.get('DATABASE_URL', settings.DATABASE_URL).rsplit('@', 1)[-1]}")
    asyncio.run(seed())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
