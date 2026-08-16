from fastapi import FastAPI

from app.api.v1.health import router as health_router
from app.api.v1.llm_profiles import router as profiles_router
from app.api.v1.media import router as media_router
from app.core.config import get_settings

settings = get_settings()
app = FastAPI(title="Aviation Maintenance Oral Exam API")
app.include_router(health_router, prefix=settings.api_v1_prefix)
app.include_router(profiles_router, prefix=settings.api_v1_prefix)
app.include_router(media_router, prefix=settings.api_v1_prefix)
