_FUNCTION_DECLARATIONS = [
    {
        "name": "get_degree_summary",
        "description": "Get the student's degree progress: credits completed and remaining per requirement bucket, percentage complete, and any at-risk buckets. Call this when you need to assess academic standing or before suggesting courses.",
        "parameters": {
            "type": "OBJECT",
            "properties": {},
        },
    },
    {
        "name": "suggest_courses",
        "description": "Get course suggestions for a given semester based on remaining degree requirements and the student's career goals. Returns a list of recommended courses with reasoning.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "semester": {
                    "type": "STRING",
                    "description": "The semester to plan for, e.g. 'Fall 2026', 'Winter 2027'",
                },
                "goal": {
                    "type": "STRING",
                    "description": "Optional focus area, e.g. 'clear science breadth', 'strengthen systems knowledge'",
                },
            },
            "required": ["semester"],
        },
    },
    {
        "name": "add_course",
        "description": "Add a course to the student's degree plan.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "course_code": {"type": "STRING", "description": "e.g. 'CIS*3490'"},
                "course_name": {"type": "STRING", "description": "e.g. 'The Analysis and Design of Computer Algorithms'"},
                "credit_value": {"type": "NUMBER", "description": "Credit weight, e.g. 0.5"},
                "requirement_bucket": {"type": "STRING", "description": "Name of the degree requirement bucket this course satisfies"},
                "term": {"type": "STRING", "description": "e.g. 'Fall 2026'"},
                "status": {"type": "STRING", "description": "One of: completed, in_progress, planned, not_scheduled"},
            },
            "required": ["course_code", "course_name", "credit_value", "requirement_bucket", "term", "status"],
        },
    },
    {
        "name": "update_course_status",
        "description": "Update the status or grade of an existing course.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "course_id": {"type": "STRING", "description": "UUID of the course"},
                "status": {"type": "STRING", "description": "One of: completed, in_progress, planned, not_scheduled"},
                "grade": {"type": "STRING", "description": "Grade received, e.g. 'A-', 'B+'"},
            },
            "required": ["course_id"],
        },
    },
    {
        "name": "create_project",
        "description": "Create a new portfolio project with milestones.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "name": {"type": "STRING", "description": "Project name"},
                "description": {"type": "STRING", "description": "Project description"},
                "priority": {"type": "INTEGER", "description": "Priority 1-3"},
                "tech_stack": {"type": "STRING", "description": "Comma-separated technologies"},
                "hard_deadline": {"type": "STRING", "description": "ISO date string, e.g. '2026-04-30'"},
                "product_framing": {"type": "STRING", "description": "What problem it solves, who the user is"},
            },
            "required": ["name", "priority"],
        },
    },
    {
        "name": "update_milestone_status",
        "description": "Update the status of a project milestone.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "milestone_id": {"type": "STRING", "description": "UUID of the milestone"},
                "status": {"type": "STRING", "description": "One of: pending, in_progress, complete, overdue"},
            },
            "required": ["milestone_id", "status"],
        },
    },
    {
        "name": "add_career_target",
        "description": "Add a target company/role to the student's career plan.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "company_name": {"type": "STRING", "description": "Company name"},
                "role_type": {"type": "STRING", "description": "e.g. 'SWE Intern', 'PM Intern'"},
                "location": {"type": "STRING", "description": "Location"},
                "target_term": {"type": "STRING", "description": "e.g. 'Summer 2027'"},
                "notes": {"type": "STRING", "description": "Additional notes"},
            },
            "required": ["company_name"],
        },
    },
    {
        "name": "update_career_target",
        "description": "Update an existing career target's status or details.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "target_id": {"type": "STRING", "description": "UUID of the career target"},
                "status": {"type": "STRING", "description": "One of: researching, applied, interviewing, offer, rejected"},
                "notes": {"type": "STRING", "description": "Updated notes"},
            },
            "required": ["target_id"],
        },
    },
    {
        "name": "flag_risk",
        "description": "Flag a risk or concern for the student. Creates a suggestion that appears on their dashboard.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "category": {"type": "STRING", "description": "One of: course, project, career, schedule, risk_flag"},
                "description": {"type": "STRING", "description": "Clear description of the risk and recommended action"},
                "severity": {"type": "STRING", "description": "One of: low, medium, high"},
            },
            "required": ["category", "description", "severity"],
        },
    },
    {
        "name": "generate_timeline",
        "description": "Create multiple timeline events at once for career plans, semester plans, or project roadmaps. Each event needs a title, event_date (ISO format), and category (one of: deadline, milestone, goal, co_op, academic).",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "events": {
                    "type": "ARRAY",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "title": {"type": "STRING"},
                            "description": {"type": "STRING"},
                            "event_date": {"type": "STRING", "description": "ISO date"},
                            "category": {"type": "STRING", "description": "One of: deadline, milestone, goal, co_op, academic"},
                            "is_hard_deadline": {"type": "BOOLEAN"},
                        },
                        "required": ["title", "event_date", "category"],
                    },
                },
            },
            "required": ["events"],
        },
    },
    {
        "name": "update_user_profile",
        "description": "Update the student's profile information. Use during onboarding to save university, program, graduation year, career target, etc.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "university": {"type": "STRING"},
                "program": {"type": "STRING"},
                "start_year": {"type": "INTEGER"},
                "expected_graduation_year": {"type": "INTEGER"},
                "country": {"type": "STRING"},
                "city": {"type": "STRING"},
                "career_target": {"type": "STRING"},
                "onboarding_complete": {"type": "BOOLEAN"},
            },
        },
    },
    {
        "name": "search_course_recommendations",
        "description": "Search for elective or optional course recommendations from the student's university that align with their career goals and degree requirements.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "focus_area": {
                    "type": "STRING",
                    "description": "Career or skill focus area, e.g. 'machine learning', 'systems programming'",
                },
                "requirement_bucket": {
                    "type": "STRING",
                    "description": "Optional: specific degree requirement bucket to fill",
                },
                "semester": {
                    "type": "STRING",
                    "description": "Target semester, e.g. 'Fall 2026'",
                },
            },
            "required": ["focus_area"],
        },
    },
    {
        "name": "search_and_recommend_courses",
        "description": "Generate personalized course recommendations for a specific semester based on the student's university, degree requirement gaps, and career goals.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "semester": {
                    "type": "STRING",
                    "description": "Target semester, e.g. 'Fall 2026'",
                },
                "goal": {
                    "type": "STRING",
                    "description": "One of: 'degree_requirement', 'career', 'both'.",
                },
                "requirement_bucket": {
                    "type": "STRING",
                    "description": "Optional: specific requirement bucket to focus on",
                },
            },
            "required": ["semester"],
        },
    },
    {
        "name": "add_degree_requirement",
        "description": "Add a degree requirement bucket (e.g. 'Major Requirements', 'Science Breadth'). Use during onboarding when the student describes their degree structure.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "bucket_name": {"type": "STRING", "description": "Name of the requirement bucket"},
                "credits_required": {"type": "NUMBER", "description": "Number of credits required"},
                "description": {"type": "STRING", "description": "Description of the requirement"},
                "notes": {"type": "STRING", "description": "Additional notes"},
            },
            "required": ["bucket_name", "credits_required"],
        },
    },
    {
        "name": "get_course_assessments",
        "description": "Get all assessments (assignments, midterms, finals, quizzes) for a specific course.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "course_code": {
                    "type": "STRING",
                    "description": "The course code to look up, e.g. 'CS1022'",
                },
            },
            "required": ["course_code"],
        },
    },
    {
        "name": "generate_semester_plan",
        "description": "Generate a complete AI-powered semester-by-semester course plan from now until graduation. Considers prerequisites, workload balance, and career alignment.",
        "parameters": {
            "type": "OBJECT",
            "properties": {},
        },
    },
]


def _convert_schema(schema: dict) -> dict:
    """Convert Gemini-style schema (uppercase types) to JSON Schema (lowercase)."""
    if not schema:
        return {"type": "object", "properties": {}}
    result = {}
    if "type" in schema:
        result["type"] = schema["type"].lower()
    if "description" in schema:
        result["description"] = schema["description"]
    if "properties" in schema:
        result["properties"] = {
            k: _convert_schema(v) for k, v in schema["properties"].items()
        }
    if "required" in schema:
        result["required"] = schema["required"]
    if "items" in schema:
        result["items"] = _convert_schema(schema["items"])
    return result


def get_groq_tools() -> list[dict]:
    """Return tool declarations in Groq/OpenAI format."""
    tools = []
    for f in _FUNCTION_DECLARATIONS:
        schema = _convert_schema(f.get("parameters", {}))
        if "properties" not in schema:
            schema["properties"] = {}
        tools.append({
            "type": "function",
            "function": {
                "name": f["name"],
                "description": f["description"],
                "parameters": schema,
            },
        })
    return tools


# Alias for any remaining references
def get_gemini_tools():
    return get_groq_tools()
