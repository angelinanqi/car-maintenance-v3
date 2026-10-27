"""Public application configuration."""
from fastapi import APIRouter
from backend import settings

router = APIRouter()


@router.get("/config")
def configuration():
    from backend.services.scopes import catalog
    knowledge = catalog()
    return {"knowledge_scopes": knowledge,
            "vehicle_scopes": [{"value": s["code"], "label": s["label"], "disabled": not s["available"]}
                               for s in knowledge if s["scope_type"] == "vehicle"],
            "chat_max_message_length": settings.CHAT_MAX_MESSAGE_LENGTH,
            "chat_history_limit": settings.CHAT_HISTORY_LIMIT,
            "api_page_size": settings.API_PAGE_SIZE,
            "image_max_bytes": settings.IMAGE_MAX_BYTES,
            "rag_configured": bool(settings.RAG_SERVICE_URL and settings.RAG_SERVICE_TOKEN)}
