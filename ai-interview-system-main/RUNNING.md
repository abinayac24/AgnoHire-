# Runtime Notes

## Target Python

Use `Python 3.11.x` for the most reliable install experience.
`Python 3.13.x` and `Python 3.14.x` are likely to fail with `nemo_toolkit[asr]`, `openai-whisper`, and some ML dependencies.

## Database

The application now uses `MongoDB` instead of `SQLite`.

Environment variables:

```text
MONGODB_URI=mongodb://localhost:27017
MONGODB_DB_NAME=ai_interview_system
ASR_PROVIDER=nemo
NEMO_ASR_MODEL=nvidia/parakeet-tdt-0.6b-v2
WHISPER_MODEL_NAME=base
SENTENCE_TRANSFORMER_MODEL=sentence-transformers/all-MiniLM-L6-v2
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@example.com
SMTP_PASSWORD=your-app-password
SMTP_USE_TLS=true
EMAIL_SENDER=your-email@example.com
RESULT_EMAIL_DELAY_SECONDS=300
```

## AI / Speech

- `sentence-transformers 3.x` for local semantic fallback evaluation
- `nemo_toolkit[asr]` with `Parakeet` is the primary backend speech-to-text path
- `openai-whisper==20240930` is optional fallback support because its dependency stack is not reliable on newer Python versions
- hosted Gemini evaluation can still be used when `GEMINI_API_KEY` is set

## Install

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Quick Local Run

From the project root, run the checked-in local launcher:

```powershell
cd E:\ai-interview-system-main\ai-interview-system-main
powershell -ExecutionPolicy Bypass -File .\start_local.ps1
```

The script starts and checks all local services:

```text
Flask UI      http://127.0.0.1:5000/
FastAPI       http://127.0.0.1:8000/api/health
Speech API    http://127.0.0.1:9000/health
```

If the health checks pass, open:

```text
http://127.0.0.1:5000/
```

For the React/Vite frontend only:

```powershell
cd frontend
npm install
npm run dev
```

Then open:

```text
http://localhost:5173/
```

## Optional ASR Setup

For backend speech-to-text, use Python 3.11 and install the optional ASR dependencies:

```powershell
pip install setuptools wheel
pip install -r requirements-optional.txt
```

Then start the app:

```powershell
python app.py
```

## Note

The current browser UI still uses browser speech recognition first.
Whisper support is optional in the backend for audio-file based transcription flows.

NeMo is configured as the preferred backend ASR provider, with Whisper as fallback if installed.
