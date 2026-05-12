import os
import tempfile
import whisper
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import health, interviews, metadata

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


# Load whisper model
whisper_model = whisper.load_model("base")

@app.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name
    try:
        result = whisper_model.transcribe(tmp_path)
        return {"text": result["text"]}
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
