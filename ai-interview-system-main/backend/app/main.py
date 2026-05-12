from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import health, interviewer, interviews, metadata, proctoring, voice, voice_verification


app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix=settings.api_prefix)
app.include_router(metadata.router, prefix=settings.api_prefix)
app.include_router(interviews.router, prefix=settings.api_prefix)
app.include_router(proctoring.router, prefix=settings.api_prefix)
app.include_router(interviewer.router, prefix=settings.api_prefix)
app.include_router(voice.router, prefix=settings.api_prefix + "/voice")
app.include_router(voice_verification.router, prefix=settings.api_prefix)
