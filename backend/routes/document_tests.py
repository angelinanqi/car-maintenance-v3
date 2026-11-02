"""Admin-only saved questions and private document previews."""
from uuid import UUID
from fastapi import APIRouter, Depends
from backend import auth
from backend.services import document_testing as testing

router = APIRouter(tags=["Document testing"], dependencies=[Depends(auth.require_admin)])


@router.get("/admin/document-test-summaries")
def summaries():
    return testing.summaries()


@router.get("/documents/{document_id}/tests")
def workspace(document_id: UUID, run_id: UUID | None = None):
    return testing.workspace(str(document_id), str(run_id) if run_id else None)


@router.post("/documents/{document_id}/tests/questions", status_code=201)
def create_question(document_id: UUID, request: testing.QuestionInput, identity=Depends(auth.require_admin)):
    return testing.save_question(str(document_id), request, identity["user"]["id"])


@router.patch("/documents/{document_id}/tests/questions/{question_id}")
def edit_question(document_id: UUID, question_id: UUID, request: testing.QuestionEdit, identity=Depends(auth.require_admin)):
    return testing.save_question(str(document_id), request, identity["user"]["id"], str(question_id))


@router.post("/documents/{document_id}/tests/questions/{question_id}/run")
async def run_question(document_id: UUID, question_id: UUID, request: testing.RunInput, identity=Depends(auth.require_admin)):
    return await testing.run_test(str(document_id), str(question_id), request, identity["user"]["id"])


@router.patch("/documents/{document_id}/tests/runs/{run_id}/review")
def review_run(document_id: UUID, run_id: UUID, request: testing.ReviewInput, identity=Depends(auth.require_admin)):
    return testing.review_run(str(document_id), str(run_id), request, identity["user"]["id"])
