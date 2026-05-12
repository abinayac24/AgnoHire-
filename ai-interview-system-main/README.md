# 🎯 AgnoHire AI Interview System

**Advanced AI-powered voice interview system with real-time proctoring, speech recognition, and intelligent evaluation**

![AgnoHire](https://img.shields.io/badge/AgnoHire-AI%20Interview-blue)
![License](https://img.shields.io/badge/License-MIT-green)
![Python](https://img.shields.io/badge/Python-3.8%2B-blue)
![JavaScript](https://imgields.io/badge/JavaScript-ES6-yellow)

## 🚀 Features

### 🎤 **Voice Interview System**
- **Real-time Speech Recognition**: OpenAI Whisper-powered STT
- **Text-to-Speech**: Browser-native TTS with fallback
- **Voice Activity Detection**: Smart silence detection
- **Live Transcription**: Real-time answer display

### 👁️ **AI Proctoring & Monitoring**
- **Face Detection**: Continuous candidate presence monitoring
- **Object Detection**: Mobile phone and multiple person detection
- **Behavioral Analysis**: Focus violation detection
- **Smart Warnings**: Non-blocking proctoring system

### 🧠 **AI Evaluation**
- **Domain-based Interviews**: Technical and role-specific questions
- **Resume-based Interviews**: Personalized from candidate CV
- **Company-specific Interviews**: Custom questions from company data
- **Intelligent Scoring**: AI-powered answer evaluation
- **Keyword Matching**: Company-specific assessment mode

### 📊 **Reporting & Analytics**
- **Real-time Feedback**: Immediate answer evaluation
- **Performance Metrics**: Detailed scoring and improvement suggestions
- **PDF Reports**: Professional interview summaries
- **Session Management**: Complete interview lifecycle tracking

### 🛡️ **Security & Reliability**
- **Interview Pause**: Automatic pause on absence
- **Anti-cheating**: Comprehensive proctoring measures
- **Data Privacy**: Secure candidate data handling
- **Fallback Systems**: Multiple redundancy layers

## 🏗️ Architecture

### **Frontend Technologies**
- **HTML5/CSS3/JavaScript**: Modern web standards
- **WebRTC**: Camera and microphone access
- **Web Audio API**: Real-time audio processing
- **Speech Synthesis API**: Browser-native TTS
- **Speech Recognition API**: Live transcription

### **Backend Services**
- **Flask**: Web UI and interview interface
- **FastAPI**: RESTful API endpoints
- **MongoDB**: Data persistence with in-memory fallback
- **Whisper**: Speech-to-text processing
- **AI Models**: Answer evaluation and scoring

### **Integration Services**
- **Voice Recognition**: OpenAI Whisper API
- **Text-to-Speech**: Browser and cloud-based TTS
- **Computer Vision**: Real-time proctoring
- **Report Generation**: PDF export functionality

## Folder Structure

```text
backend/
  app/
    config.py
    dependencies.py
    main.py
    models.py
    routers/
      health.py
      interviews.py
      metadata.py
database/
  mongo.py
modules/
  ai_evaluator.py
  keyword_matcher.py
  question_extractor.py
  report_generator.py
  resume_parser.py
  voice_handler.py
frontend/
  src/
    components/
    hooks/
    lib/
    pages/
```

## Backend API Routes

- `GET /api/health`
- `GET /api/metadata/domains`
- `POST /api/interviews/legacy/start`
- `GET /api/interviews/{session_id}`
- `GET /api/interviews/{session_id}/upcoming`
- `POST /api/interviews/{session_id}/answer`
- `POST /api/interviews/{session_id}/events`
- `POST /api/interviews/{session_id}/terminate`
- `GET /api/interviews/{session_id}/completion`
- `GET /api/interviews/{session_id}/report`
- `GET /api/interviews/{session_id}/report/pdf`
- `GET /api/proctoring/health`
- `POST /api/proctoring/analyze-frame`

## MongoDB Collections

- `Users`
- `Questions`
- `CompanyQuestions`
- `InterviewResults`
- `InterviewSessions`

Each answer record in `InterviewResults` stores:

- `candidate_name`
- `question`
- `user_answer`
- `score`
- `feedback`
- `improvement_suggestion`
- `timestamp`

## 🚀 Quick Start

### **Windows Setup (Recommended)**

```powershell
# Clone the repository
git clone https://github.com/abinayac24/AgnoHire-.git
cd AgnoHire-

# Start all services automatically
powershell -ExecutionPolicy Bypass -File .\start_local.ps1
```

The launcher automatically starts:
- **Flask UI** at `http://127.0.0.1:5000/`
- **FastAPI Backend** at `http://127.0.0.1:8000/api/health`
- **Speech Service** at `http://127.0.0.1:9000/health`

Open the application at: **http://127.0.0.1:5000/**

### **Manual Setup**

#### **Prerequisites**
- Python 3.8+ 
- Node.js 16+ (for frontend development)
- MongoDB (optional, uses in-memory fallback)

#### **Environment Setup**
```bash
# Create virtual environment
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your configuration
```

#### **Start Services**
```bash
# Start MongoDB (or use in-memory fallback)
export USE_IN_MEMORY_DB="true"

# Start FastAPI backend
cd backend
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# Start Flask UI (in new terminal)
cd backend
python app.py

# Start Speech Service (in new terminal)
cd speech
python speech_server.py
```

### **Docker Setup**
```bash
# Build and run with Docker Compose
docker-compose up -d
```

## 📋 Requirements

### **System Requirements**
- **OS**: Windows 10+, macOS 10.15+, Ubuntu 18.04+
- **RAM**: Minimum 4GB, Recommended 8GB
- **Storage**: Minimum 2GB free space
- **Network**: Internet connection for AI services

### **Browser Requirements**
- **Chrome 90+** (Recommended)
- **Microsoft Edge 90+**
- **Firefox 88+** (Limited support)
- **Safari 14+** (Limited support)

### **Hardware Requirements**
- **Microphone**: Required for voice input
- **Camera**: Required for proctoring
- **Speakers/Headphones**: Required for audio output

## 🔧 Configuration

### **Environment Variables**
```bash
# Database Configuration
MONGODB_URI=mongodb://localhost:27017/agnohire
USE_IN_MEMORY_DB=false

# API Keys (Optional)
OPENAI_API_KEY=your_openai_key
GEMINI_API_KEY=your_gemini_key

# Service Configuration
FLASK_HOST=127.0.0.1
FLASK_PORT=5000
FASTAPI_HOST=127.0.0.1
FASTAPI_PORT=8000
SPEECH_PORT=9000

# Proctoring Settings
PROCTORING_ENABLED=true
FACE_DETECTION_THRESHOLD=0.5
VAD_SPEECH_THRESHOLD=0.018
```

### **Interview Configuration**
- **Question Time**: 60 seconds per question
- **Silence Detection**: 1.4 seconds
- **Face Absence Timeout**: 2.5 seconds
- **Max Warnings**: 3 per violation type

## 🎯 Usage Guide

### **Starting an Interview**
1. Open the application at `http://127.0.0.1:5000/`
2. Allow camera and microphone permissions
3. Choose interview type (Domain/Resume/Company)
4. Upload required files (resume/company data)
5. Start the interview

### **During Interview**
- **Speak clearly** into the microphone
- **Maintain eye contact** with camera
- **Stay in frame** throughout the interview
- **Use voice commands** like "submit answer" when ready
- **Click submit button** for manual answer submission

### **Voice Commands**
- `"submit answer"` - Submit current answer
- `"repeat question"` - Hear the question again
- `"skip question"` - Move to next question
- `"next question"` - Skip current question

### **After Interview**
- View real-time feedback and scores
- Download PDF report
- Review performance metrics
- Access improvement suggestions

## 📚 API Documentation

### **Core Interview API**
```http
GET  /api/health                          # Health check
POST /api/interviews/legacy/start         # Start interview session
GET  /api/interviews/{session_id}         # Get interview details
GET  /api/interviews/{session_id}/upcoming # Get next question
POST /api/interviews/{session_id}/answer   # Submit answer
POST /api/interviews/{session_id}/events   # Log events
POST /api/interviews/{session_id}/terminate # End interview
GET  /api/interviews/{session_id}/completion # Get completion status
GET  /api/interviews/{session_id}/report  # Get interview report
GET  /api/interviews/{session_id}/report/pdf # Download PDF report
```

### **Metadata API**
```http
GET  /api/metadata/domains                 # Available interview domains
GET  /api/metadata/companies               # Company information
GET  /api/metadata/questions               # Question database
```

### **Proctoring API**
```http
GET  /api/proctoring/health                # Proctoring service health
POST /api/proctoring/analyze-frame         # Analyze camera frame
POST /api/proctoring/alert                 # Log proctoring alerts
```

### **Speech Services API**
```http
POST /voice/transcribe                      # Speech-to-text
POST /voice/verify-interview               # Voice verification
GET  /voice/health                         # Speech service health
POST /voice/speak                          # Text-to-speech
```

### **Interviewer API**
```http
POST /api/interviewer/render               # Generate AI interviewer media
GET  /api/interviewer/health               # Interviewer service health
```

## 🔧 Troubleshooting

### **Common Issues**

#### **Camera/Microphone Not Working**
```bash
# Check browser permissions
# Ensure HTTPS or localhost
# Update browser to latest version
# Try different browser (Chrome recommended)
```

#### **Speech Recognition Not Working**
```bash
# Check microphone permissions
# Ensure quiet environment
# Test with different microphone
# Check network connectivity
```

#### **Services Not Starting**
```bash
# Check port availability
netstat -an | findstr :5000
netstat -an | findstr :8000
netstat -an | findstr :9000

# Kill existing processes
taskkill /PID <pid> /F

# Restart services
powershell -ExecutionPolicy Bypass -File .\start_local.ps1
```

#### **Database Connection Issues**
```bash
# Use in-memory database
export USE_IN_MEMORY_DB="true"

# Check MongoDB connection
mongosh --eval "db.adminCommand('ismaster')"

# Restart with clean state
rm -rf .data/
```

#### **Interview Not Progressing**
```bash
# Check face detection
# Ensure camera is working
# Verify answer submission
# Check console for errors
```

### **Error Messages**

#### **"Cannot submit answer, please ensure you are visible in camera"**
- Check camera permissions
- Ensure face is visible
- Restart interview if needed

#### **"Voice not recognized"**
- Speak clearly and loudly
- Check microphone quality
- Reduce background noise
- Try manual submission

#### **"Interview paused"**
- Return to camera frame
- Ensure face is detected
- Wait for automatic resume

### **Performance Optimization**

#### **Reduce Latency**
```bash
# Use local Whisper model
# Optimize audio buffer size
# Reduce VAD polling frequency
# Enable browser caching
```

#### **Memory Usage**
```bash
# Clear browser cache
# Restart services periodically
# Use in-memory database for testing
# Monitor system resources
```

## 🤝 Contributing

### **Development Setup**
```bash
# Clone repository
git clone https://github.com/abinayac24/AgnoHire-.git
cd AgnoHire-

# Setup development environment
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

# Install pre-commit hooks
pre-commit install
```

### **Code Style**
- **Python**: Follow PEP 8
- **JavaScript**: Use ESLint configuration
- **HTML**: Use semantic HTML5
- **CSS**: Follow BEM methodology

### **Testing**
```bash
# Run backend tests
pytest backend/tests/

# Run frontend tests
cd frontend
npm test

# Run integration tests
python -m pytest tests/integration/
```

### **Pull Request Process**
1. Fork the repository
2. Create feature branch
3. Make changes with tests
4. Submit pull request
5. Wait for code review

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **OpenAI** - Whisper speech recognition
- **Google** - Web Speech API
- **Mozilla** - WebRTC standards
- **FastAPI** - Backend framework
- **Flask** - Web framework

## 📞 Support

### **Getting Help**
- **Documentation**: Check this README first
- **Issues**: Report on [GitHub Issues](https://github.com/abinayac24/AgnoHire-/issues)
- **Discussions**: Join [GitHub Discussions](https://github.com/abinayac24/AgnoHire-/discussions)

### **Contact**
- **Email**: support@agnohire.com
- **GitHub**: @abinayac24
- **Website**: https://agnohire.com

---

**🎯 AgnoHire - Revolutionizing interviews with AI**
