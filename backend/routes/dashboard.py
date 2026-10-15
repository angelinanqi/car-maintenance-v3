from collections import Counter
from fastapi import APIRouter, Depends
from backend import auth, db
from backend.models import Dashboard

router = APIRouter(tags=["Dashboard"], dependencies=[Depends(auth.require_admin)])


@router.get("/dashboard", response_model=Dashboard)
def dashboard():
    documents = db.all_rows("documents")
    guides = db.all_rows("guides")
    playbooks = db.all_rows("emergency_playbooks")
    return {
        "documents": dict(total=len(documents), **Counter(row["status"] for row in documents)),
        "guides": dict(total=len(guides), **Counter(row["status"] for row in guides)),
        "playbooks": len(playbooks),
        "steps": sum(len(row["steps"]) for row in playbooks),
        "contacts": len(db.all_rows("emergency_contacts")),
    }
