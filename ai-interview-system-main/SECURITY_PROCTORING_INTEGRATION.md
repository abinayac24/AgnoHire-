# Security & Proctoring Warning System Integration

This document summarizes the comprehensive warning system integration across the AI Interview System's security and proctoring infrastructure.

## 📁 Files Created/Modified

### Backend Files

#### 1. `backend/app/routers/proctoring.py` (MODIFIED)
**Added Features:**
- `WarningConnectionManager` class for WebSocket broadcast management
- Real-time warning broadcasting to all connected clients
- Session-based warning tracking with strike counting
- Auto-reconnection handling for WebSocket clients
- Warning severity classification (warning/critical)

**Key Functions:**
- `broadcast_warning(session_id, warning_data)` - Broadcasts warnings to all clients
- `connect(session_id, websocket)` - Registers WebSocket connections
- `disconnect(session_id, websocket)` - Cleans up disconnected clients

#### 2. `backend/app/routers/interviews.py` (MODIFIED)
**Added Features:**
- `/api/enrollment` endpoint for biometric registration
- Face embedding extraction from enrollment samples
- Integration with identity verifier for registration
- Enrollment data storage

**Key Classes:**
- `EnrollmentRequest` - Pydantic model for enrollment data

### Frontend Files

#### 3. `frontend/src/hooks/useProctoring.js` (NEW)
**Purpose:** React hook for proctoring integration

**Features:**
- WebSocket connection management with auto-reconnect
- Frame capture and transmission to backend (every 2 seconds)
- Warning state management
- Strike counting and tracking
- Interview termination handling
- Connection status monitoring

**Key Exports:**
- `useProctoring(sessionId, onTermination)` hook

#### 4. `frontend/src/components/ProctoringWarning.jsx` (NEW)
**Purpose:** Visual warning popup components

**Components:**
- `ProctoringWarning` - Full-screen warning modal with:
  - Animated progress bar (6-second auto-dismiss)
  - Rule-specific icons and colors
  - Strike counter visualization
  - Warning severity indicators
  - "I Understand" dismiss button

- `ProctoringStatus` - Compact status bar showing:
  - Proctoring connection status
  - Strike count badge
  - Real-time monitoring indicator

**Warning Types Supported:**
- mobile_phone (📱)
- multi_person (👥)
- identity_mismatch (🚫)
- eye_gaze (👀)
- head_pose (🔄)
- partial_human (👤)
- assistance_suspected (🆘)
- reading_pattern (📖)

#### 5. `frontend/src/pages/SessionPage.jsx` (MODIFIED)
**Integration Points:**
- Added `useProctoring` hook integration
- Added `ProctoringWarning` and `ProctoringStatus` components
- Proctoring start/stop lifecycle management
- Interview termination handling
- Warning display in interview UI

#### 6. `frontend/src/pages/EnrollmentPage.jsx` (NEW)
**Purpose:** Biometric enrollment for identity verification

**Enrollment Steps:**
1. **Camera Setup** - User enters name, camera permission
2. **Face Capture** - 5 face samples from different angles
3. **Voice Capture** - 4 voice samples (5 seconds each)
4. **Complete** - Review and submit enrollment

**Features:**
- Live camera preview with face positioning guide
- Visual progress indicators
- Audio recording with visual feedback
- Sample validation and storage

#### 7. `frontend/src/pages/AdminDashboard.jsx` (NEW)
**Purpose:** Admin interface for security monitoring and incident review

**Tabs:**
1. **Overview** - System health, session counts, daily incidents
2. **Sessions** - List of all interview sessions with violation counts
3. **Incidents** - Security alert timeline with details
4. **Analytics** - Violation type distribution, system health metrics

**Features:**
- Real-time session monitoring
- Alert detail viewing with detection metadata
- Strike visualization per incident
- Session detail modal with complete alert history
- Model availability status (YOLO, Face Detection)

#### 8. `frontend/src/App.jsx` (MODIFIED)
**Added Routes:**
- `/enrollment` - Biometric enrollment page
- `/admin` - Admin dashboard

## 🔄 Warning Flow Architecture

```
┌─────────────────┐
│  Webcam Stream  │
└────────┬────────┘
         │
┌────────▼────────┐     ┌──────────────────┐
│ Proctoring      │────→│ WebSocket Server │
│ Engine          │     │ (WarningManager) │
│ (YOLO/Face/     │     └────────┬─────────┘
│  Identity)      │              │
└─────────────────┘              │ Broadcast
                                 │
                    ┌────────────▼────────────┐
                    │   Frontend Clients      │
                    │  ┌───────────────────┐  │
                    │  │ useProctoring Hook │  │
                    │  │  - Receives warnings │  │
                    │  │  - Updates state     │  │
                    │  │  - Triggers UI       │  │
                    │  └─────────┬─────────┘  │
                    │            │            │
                    │  ┌─────────▼─────────┐  │
                    │  │ ProctoringWarning │  │
                    │  │   Component       │  │
                    │  │  - Visual popup   │  │
                    │  │  - TTS synthesis  │  │
                    │  │  - Auto-dismiss   │  │
                    │  └───────────────────┘  │
                    └─────────────────────────┘
```

## 🎯 3-Strike Warning System

### Strike Progression:
```
Strike 1 (Yellow): Warning popup with caution message
         ↓
Strike 2 (Orange): "FINAL WARNING" - Urgent visual style
         ↓
Strike 3 (Red): Interview termination triggered
```

### Backend Strike Rules:
```python
STRIKE_RULES = {
    "mobile_phone", "multi_person", "voice_identity", 
    "voice_multi_speaker", "face_absence", "replacement_detected",
    "fullscreen_exit", "focus_violation", "eye_gaze", "head_pose", "partial_human"
}
```

## 🔌 API Endpoints

### New Endpoints:

1. **WebSocket** `ws://api/proctoring/ws`
   - Bidirectional communication for real-time proctoring
   - Frame upload and alert broadcast

2. **POST** `/api/enrollment`
   - Biometric registration
   - Face/voice sample submission

3. **GET** `/api/proctoring/health`
   - System health status
   - Model availability

4. **GET** `/api/proctoring/alerts/{session_id}`
   - Session alert history
   - 200 alert limit with pagination

## 🎨 UI/UX Specifications

### Warning Popup Design:
- **Position**: Center screen with dark backdrop
- **Animation**: Pulse effect for critical warnings
- **Duration**: 6 seconds auto-dismiss
- **Colors**: 
  - Critical: Red gradient (#dc2626 to #991b1b)
  - Warning: Orange gradient
  - Backdrop: Black/70% opacity with blur

### Status Bar Design:
- **Position**: Top-right of interview panel
- **Size**: Compact pill shape
- **Indicators**: 
  - Green dot: Connected
  - Red dot: Disconnected
  - Strike counter badge

## 🔒 Security Features

### Biometric Verification:
- **FaceNet512** embeddings for face matching
- **Cosine Similarity** threshold: 0.65
- **Replacement Detection** threshold: 0.40

### Liveness Detection:
- **MediaPipe Face Mesh** for pose tracking
- **Eye Aspect Ratio (EAR)** for blink detection
- **Yaw/Pitch** tracking for head movement

### Object Detection:
- **YOLOv8** for real-time object detection
- **Confidence Thresholds**:
  - Phone: 0.05 (very sensitive)
  - Person: 0.10
- **Cooldown**: 8 seconds between warnings

## 📊 Monitoring & Analytics

### Admin Dashboard Metrics:
- Total sessions and active proctoring status
- Violation type distribution
- Daily incident counts
- Model availability tracking
- Session termination reasons

### Alert Storage:
- MongoDB/Motor async storage
- Session-based organization
- Alert metadata with detection details
- Warning count tracking per rule

## 🚀 Usage Instructions

### For Candidates:
1. Navigate to `/enrollment`
2. Enter name and allow camera access
3. Capture 5 face samples
4. Record 4 voice samples
5. Start interview at `/session/{id}`
6. View warnings in real-time during interview

### For Admins:
1. Navigate to `/admin`
2. View Overview tab for system status
3. Check Sessions tab for all interviews
4. Review Incidents tab for security alerts
5. Click session rows for detailed timeline

## 🔧 Configuration

### Environment Variables:
```bash
VITE_API_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000
```

### Backend Settings:
```python
VISION_ALERT_COOLDOWN_MS = 8000  # 8 seconds
MAX_WARNINGS_PER_RULE = 3
PHONE_DETECTION_CONFIDENCE = 0.05
PERSON_DETECTION_CONFIDENCE = 0.10
```

## 📝 Testing

### Test Warning System:
1. Start interview session
2. Show phone to camera
3. Verify red popup appears with "Strike 1 of 3"
4. Check console for `[TRIGGER WARNING]` logs
5. Verify TTS warning plays
6. Check WebSocket messages in Network tab

### Test Enrollment:
1. Navigate to `/enrollment`
2. Complete all 3 steps
3. Verify enrollment data stored
4. Check face embedding registered

---

**Integration Complete**: All warning system components are now integrated across the AI Interview System's security infrastructure.
