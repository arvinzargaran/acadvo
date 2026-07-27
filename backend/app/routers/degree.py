import logging
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile

logger = logging.getLogger(__name__)
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.limiter import limiter
from app.models.user import User
from app.schemas.degree import (
    AssessmentResponse,
    CourseCreate,
    CourseResponse,
    CourseUpdate,
    CredentialCreate,
    CredentialResponse,
    CredentialUpdate,
    DegreeRequirementCreate,
    DegreeRequirementResponse,
    DegreeRequirementUpdate,
    DegreeSummaryResponse,
    GPAResponse,
    ParsedDegreeDocument,
)
from app.services import degree as degree_service
from app.services.document_parser import parse_degree_document

router = APIRouter()

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/webp",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
    "text/csv",
}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


# ── Document Parsing ─────────────────────────────────────────────────

@router.post("/parse-document", response_model=ParsedDegreeDocument)
@limiter.limit("5/hour")
async def parse_document(
    request: Request,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file.content_type}. Accepted: PDF, PNG, JPEG, WebP, Excel, CSV.",
        )

    if file.size is not None and file.size > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large. Maximum size is 10 MB.")
    file_bytes = await file.read()
    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large. Maximum size is 10 MB.")

    try:
        result = await parse_degree_document(file_bytes, file.content_type)
    except Exception as e:
        logger.error("Document parse error: %s", e)
        err_str = str(e)
        if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "quota" in err_str.lower():
            raise HTTPException(
                status_code=429,
                detail="AI service is temporarily unavailable due to rate limits. Please try again later.",
            )
        raise HTTPException(
            status_code=422,
            detail="Could not parse document. Please ensure it is a valid degree checklist or transcript.",
        )

    return result


# ── GPA ──────────────────────────────────────────────────────────────

@router.get("/gpa", response_model=GPAResponse)
async def get_gpa(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await degree_service.calculate_gpa(current_user.id, db)


# ── Summary ──────────────────────────────────────────────────────────

@router.get("/summary", response_model=DegreeSummaryResponse)
async def degree_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await degree_service.get_degree_summary(current_user.id, db)


# ── Requirements ─────────────────────────────────────────────────────

@router.get("/requirements", response_model=list[DegreeRequirementResponse])
async def list_requirements(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await degree_service.list_requirements(current_user.id, db)


@router.post("/requirements", response_model=DegreeRequirementResponse, status_code=201)
async def create_requirement(
    data: DegreeRequirementCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await degree_service.create_requirement(current_user.id, data, db)


@router.put("/requirements/{requirement_id}", response_model=DegreeRequirementResponse)
async def update_requirement(
    requirement_id: uuid.UUID,
    data: DegreeRequirementUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await degree_service.update_requirement(requirement_id, current_user.id, data, db)


# ── Courses ──────────────────────────────────────────────────────────

@router.get("/courses", response_model=list[CourseResponse])
async def list_courses(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await degree_service.list_courses(current_user.id, db)


@router.post("/courses", response_model=CourseResponse, status_code=201)
async def create_course(
    data: CourseCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await degree_service.create_course(current_user.id, data, db)


@router.put("/courses/{course_id}", response_model=CourseResponse)
async def update_course(
    course_id: uuid.UUID,
    data: CourseUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await degree_service.update_course(course_id, current_user.id, data, db)


@router.delete("/courses/{course_id}", status_code=204)
async def delete_course(
    course_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await degree_service.delete_course(course_id, current_user.id, db)


# ── Assessments / Syllabus Parsing ────────────────────────────────────

@router.get("/courses/{course_id}/assessments", response_model=list[AssessmentResponse])
async def list_assessments(
    course_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await degree_service.list_assessments(course_id, current_user.id, db)


@router.post("/courses/{course_id}/parse-syllabus", response_model=list[AssessmentResponse])
@limiter.limit("10/hour")
async def parse_syllabus(
    request: Request,
    course_id: uuid.UUID,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file.content_type}. Accepted: PDF, PNG, JPEG, WebP.",
        )

    if file.size is not None and file.size > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large. Maximum size is 10 MB.")
    file_bytes = await file.read()
    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large. Maximum size is 10 MB.")

    try:
        assessments = await degree_service.parse_and_save_syllabus(
            course_id, current_user.id, file_bytes, file.content_type, db
        )
    except Exception:
        logger.exception("Syllabus parse error")
        raise HTTPException(
            status_code=422,
            detail="Could not parse syllabus. Please ensure it is a valid course outline.",
        )

    return assessments


# ── Credentials ──────────────────────────────────────────────────────

@router.get("/credentials", response_model=list[CredentialResponse])
async def list_credentials(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await degree_service.list_credentials(current_user.id, db)


@router.post("/credentials", response_model=CredentialResponse, status_code=201)
async def create_credential(
    data: CredentialCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await degree_service.create_credential(current_user.id, data, db)


@router.put("/credentials/{credential_id}", response_model=CredentialResponse)
async def update_credential(
    credential_id: uuid.UUID,
    data: CredentialUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await degree_service.update_credential(credential_id, current_user.id, data, db)


@router.delete("/credentials/{credential_id}", status_code=204)
async def delete_credential(
    credential_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await degree_service.delete_credential(credential_id, current_user.id, db)
