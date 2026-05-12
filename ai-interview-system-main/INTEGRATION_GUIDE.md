# AI Interview System - Integration Guide

## System Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Frontend      │────▶│  Main API       │────▶│   Database      │
│   (Port 5000)   │     │  (Port 8000)    │     │  (MongoDB)      │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                               │
                               ▼
                        ┌─────────────────┐
                        │ Speech Service  │
                        │ (Port 9000)     │
                        └─────────────────┘
```

## Service Details

### 1. Frontend (Flask) - Port 5000
- **Location**: `d:\Interview_System\AI_Interview_System\app.py`
- **Virtual Env**: `venv310_win`
- **Purpose**: Serves React frontend and handles session management

### 2. Main API (FastAPI) - Port 8000
- **Location**: `d:\Interview_System\AI_Interview_System\app\main.py`
- **Virtual Env**: `venv310_win`
- **Purpose**: Core API for interviews, questions, reports

### 3. Speech Service (FastAPI) - Port 9000
- **Location**: `d:\Interview_System\AI_Interview_System\backend\app\main.py`
- **Virtual Env**: `backend\venv`
- **Purpose**: Whisper transcription service

## Quick Start Commands

### Terminal 1 - Main API (Port 8000)
```powershell
cd d:\Interview_System\AI_Interview_System
$env:PYTHONPATH = "d:\Interview_System\AI_Interview_System"
.\venv310_win\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### Terminal 2 - Speech Service (Port 9000)
```powershell
cd d:\Interview_System\AI_Interview_System\backend
.\venv\Scripts\Activate.ps1
uvicorn app.main:app --port 9000 --host 127.0.0.1 --reload
```

### Terminal 3 - Frontend (Port 5000)
```powershell
cd d:\Interview_System\AI_Interview_System
$env:USE_IN_MEMORY_DB = "true"
.\venv310_win\Scripts\python.exe app.py
```

## API Endpoints

### Interview Management
- `POST /api/interviews/domain/start` - Start domain interview
- `POST /api/interviews/resume/start` - Start resume-based interview
- `POST /api/interviews/company/start` - Start company interview
- `GET /api/interviews/{session_id}` - Get session details
- `POST /api/interviews/{session_id}/answer` - Submit answer
- `GET /api/interviews/{session_id}/report` - Get report
- `GET /api/interviews/{session_id}/report/pdf` - Download PDF

### Health & Metadata
- `GET /api/health` - Health check
- `GET /api/metadata/domains` - Get available domains

### Speech (Port 9000)
- `POST /transcribe` - Audio transcription

## Frontend Integration

### React Components
- `SessionPage.jsx` - Interview session page
- `InterviewPanel.jsx` - Question/answer UI
- `useSpeechRecognition.js` - Voice recognition hook
- `useSpeechSynthesis.js` - Text-to-speech hook

### API Client
Located at `frontend/src/lib/api.js`:
```javascript
export async function startDomainInterview(candidateName, domain) { ... }
export async function submitInterviewAnswer(sessionId, answer) { ... }
export async function getInterviewSession(sessionId) { ... }
```

## Environment Variables

Create `.env` in project root:
```
GEMINI_API_KEY=your_key_here
MONGODB_URI=mongodb://localhost:27017
MONGODB_DB_NAME=ai_interview_system
USE_IN_MEMORY_DB=true
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_USE_TLS=true
EMAIL_SENDER=your-email@gmail.com
```

## Database Schema

### Collections
- `InterviewSessions` - Active interview sessions
- `InterviewResults` - Answers and evaluations
- `Users` - Candidate information
- `Questions` - Question bank
- `CompanyQuestions` - Company-specific questions

## Integration Checklist

- [ ] All three services running
- [ ] Frontend accessible at http://127.0.0.1:5000
- [ ] Main API responding at http://127.0.0.1:8000/api/health
- [ ] Speech service at http://127.0.0.1:9000
- [ ] Microphone permissions granted in browser
- [ ] Test voice recognition working
- [ ] Test interview flow end-to-end

## Troubleshooting

### Port Already in Use
```powershell
netstat -ano | findstr ":8000|:9000|:5000"
taskkill /PID <process_id> /F
```

### Import Errors
Ensure `PYTHONPATH` is set correctly:
```powershell
$env:PYTHONPATH = "d:\Interview_System\AI_Interview_System"
```

### CORS Errors
Check `app/config.py` - CORS origins include localhost ports.

### Voice Not Recognized
1. Check browser console for errors
2. Verify microphone permission granted
3. Ensure speech service running on port 9000
4. Check `useSpeechRecognition.js` for interim results

## File Structure

```
AI_Interview_System/
├── app.py                    # Flask frontend entry
├── app/                      # Main API
│   ├── main.py              # FastAPI app
│   ├── config.py            # Settings
│   ├── routers/             # API routes
│   ├── services/            # Service layer
│   └── modules/             # Core modules
├── backend/                 # Speech service
│   ├── app/
│   │   ├── main.py         # FastAPI entry
│   │   ├── modules/        # Speech modules
│   │   └── services/       # Service wrappers
│   └── venv/               # Backend virtual env
├── frontend/               # React frontend
│   ├── src/
│   │   ├── components/     # UI components
│   │   ├── hooks/          # React hooks
│   │   ├── pages/          # Page components
│   │   └── lib/            # API clients
│   └── dist/               # Build output
├── venv310_win/           # Main virtual env
└── .env                    # Environment variables
```

## Dependencies

### Main Virtual Env (venv310_win)
- fastapi, uvicorn
- flask, requests
- torch, whisper
- pymongo, python-dotenv
- reportlab, PyPDF2
- pandas, pdfplumber
- sentence-transformers

### Backend Virtual Env (backend/venv)
- fastapi, uvicorn
- whisper, torch
- pandas, pdfplumber
- reportlab, pymongo

## Browser Compatibility

Voice recognition requires:
- Chrome 89+ or Edge 89+
- Microphone access permission
- HTTPS for production (localhost OK for dev)

## Support

For issues:
1. Check service logs in terminal
2. Open browser console (F12) for frontend errors
3. Verify all ports accessible
4. Check `.env` configuration
