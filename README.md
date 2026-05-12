# AgnoHire - AI Interview System

**AgnoHire** is an advanced, fully automated, voice-based AI interview platform designed to seamlessly conduct, proctor, and evaluate technical and behavioral interviews.

## 🚀 Features

- **Conversational AI Interviewing:** Fully automated, timer-based question progression with continuous voice recording and seamless AI-driven interactions.
- **Robust Proctoring Engine:** Real-time monitoring to ensure interview integrity.
  - Face Verification & Authentication
  - Multi-person Detection (with robust validation pipelines and temporal persistence)
  - Unauthorized Device Detection (filtering out the primary laptop/camera)
- **Voice Commands:** Intelligent transcript processing to detect user intents (e.g., saying "Next question" or "I don't know" to skip).
- **Speech Services Integration:** Powered by advanced speech-to-text (Whisper) and text-to-speech technologies for low-latency voice interactions.
- **Admin Dashboard:** Comprehensive reporting, analytics, and interview evaluation tools.
- **Voice Password Authentication:** Secure voice-based login and registration.

## 🛠️ Technology Stack

- **Backend:** Python, FastAPI, MongoDB
- **Frontend:** HTML5, Vanilla CSS, JavaScript
- **AI & ML:** Computer Vision (OpenCV, YOLO/MediaPipe for proctoring), OpenAI Whisper (Transcription), SpeechBrain

## ⚙️ Getting Started

### Prerequisites

Ensure you have Python installed (v3.8+ recommended) and the required packages.

### Installation & Running Locally

The project includes convenient startup scripts to launch all integrated services (Backend, Frontend, Speech Service).

1. Clone the repository:
   ```bash
   git clone https://github.com/abinayac24/AgnoHire-.git
   cd AgnoHire-
   ```

2. Run the platform using the local startup script:
   ```bash
   # On Windows
   start_local.bat
   ```
   *Note: This will install necessary dependencies, activate the virtual environment, and concurrently start the API servers and UI.*

## 🔒 Proctoring Rules
The automated proctoring engine ensures high integrity by monitoring:
1. **Face Presence:** Ensures the candidate remains in the frame.
2. **Device Detection:** Flags unauthorized devices (like phones) while correctly ignoring the primary laptop.
3. **Multi-Person Detection:** Triggers warnings if a secondary person is identified with high confidence over a sustained period.

## 📝 License
This project is proprietary and built for AgnoHire. All rights reserved.