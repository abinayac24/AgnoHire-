import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Shell } from "../components/Shell";

const ENROLLMENT_STEPS = {
  CAMERA: "camera",
  FACE: "face",
  VOICE: "voice",
  COMPLETE: "complete",
};

export function EnrollmentPage() {
  const navigate = useNavigate();
  const [step, setStep] = useState(ENROLLMENT_STEPS.CAMERA);
  const [sessionId, setSessionId] = useState("");
  const [username, setUsername] = useState("");
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState(null);
  const [progress, setProgress] = useState(0);
  
  const [faceSamples, setFaceSamples] = useState([]);
  const [voiceSamples, setVoiceSamples] = useState([]);
  
  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const mediaRecorderRef = useRef(null);

  // Initialize camera
  useEffect(() => {
    const initCamera = async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { width: 640, height: 480, facingMode: "user" },
          audio: false,
        });
        streamRef.current = stream;
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
        }
      } catch (err) {
        setError("Camera access denied. Please allow camera access to proceed.");
      }
    };

    if (step === ENROLLMENT_STEPS.CAMERA || step === ENROLLMENT_STEPS.FACE) {
      initCamera();
    }

    return () => {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(track => track.stop());
      }
    };
  }, [step]);

  // Generate session ID
  useEffect(() => {
    const generatedId = `enroll_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    setSessionId(generatedId);
  }, []);

  const captureFaceSample = useCallback(() => {
    if (!videoRef.current) return;
    
    const canvas = document.createElement("canvas");
    canvas.width = videoRef.current.videoWidth;
    canvas.height = videoRef.current.videoHeight;
    const ctx = canvas.getContext("2d");
    ctx.drawImage(videoRef.current, 0, 0, canvas.width, canvas.height);
    
    const imageData = canvas.toDataURL("image/jpeg", 0.9);
    setFaceSamples(prev => [...prev, imageData]);
    
    // Visual feedback
    setProgress((prev) => {
      const next = prev + 20;
      if (next >= 100) {
        setTimeout(() => setStep(ENROLLMENT_STEPS.VOICE), 500);
        return 100;
      }
      return next;
    });
  }, []);

  const startVoiceRecording = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream);
      const chunks = [];
      
      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunks.push(e.data);
      };
      
      mediaRecorder.onstop = () => {
        const blob = new Blob(chunks, { type: "audio/webm" });
        const reader = new FileReader();
        reader.onloadend = () => {
          setVoiceSamples(prev => [...prev, reader.result]);
          setProgress(prev => {
            const next = prev + 25;
            if (next >= 100) {
              setTimeout(() => setStep(ENROLLMENT_STEPS.COMPLETE), 500);
              return 100;
            }
            return next;
          });
        };
        reader.readAsDataURL(blob);
      };
      
      mediaRecorderRef.current = mediaRecorder;
      mediaRecorder.start();
      
      // Auto-stop after 5 seconds
      setTimeout(() => {
        if (mediaRecorder.state === "recording") {
          mediaRecorder.stop();
          stream.getTracks().forEach(track => track.stop());
        }
      }, 5000);
      
    } catch (err) {
      setError("Microphone access denied. Please allow microphone access.");
    }
  }, []);

  const submitEnrollment = useCallback(async () => {
    setIsProcessing(true);
    setError(null);
    
    try {
      const response = await fetch(`${import.meta.env.VITE_API_URL || "http://localhost:8000"}/api/enrollment`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          username: username || "candidate",
          face_samples: faceSamples,
          voice_samples: voiceSamples,
          timestamp: new Date().toISOString(),
        }),
      });
      
      if (!response.ok) {
        throw new Error("Failed to submit enrollment data");
      }
      
      // Navigate to interview after successful enrollment
      setTimeout(() => {
        navigate(`/interview?session=${sessionId}`);
      }, 1500);
      
    } catch (err) {
      setError(err.message);
      setIsProcessing(false);
    }
  }, [sessionId, username, faceSamples, voiceSamples, navigate]);

  // Camera setup step
  if (step === ENROLLMENT_STEPS.CAMERA) {
    return (
      <Shell>
        <div className="max-w-2xl mx-auto">
          <div className="glass-panel rounded-[28px] p-8 text-center">
            <h1 className="text-3xl font-bold text-white mb-4">
              Identity Enrollment
            </h1>
            <p className="text-slate-300 mb-8">
              We need to capture your biometric data for identity verification during the interview.
              This ensures exam integrity and prevents impersonation.
            </p>
            
            <div className="mb-8">
              <div className="w-48 h-48 mx-auto bg-slate-700 rounded-full flex items-center justify-center mb-4">
                <span className="text-6xl">📷</span>
              </div>
              <p className="text-cyan-300 font-semibold">Step 1 of 3: Camera Setup</p>
            </div>

            <div className="space-y-4">
              <input
                type="text"
                placeholder="Enter your full name"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="w-full px-4 py-3 rounded-xl bg-slate-800 border border-slate-600 text-white placeholder-slate-400 focus:border-cyan-400 focus:outline-none"
              />
              
              <button
                onClick={() => setStep(ENROLLMENT_STEPS.FACE)}
                disabled={!username.trim()}
                className="w-full py-4 px-6 bg-gradient-to-r from-cyan-500 to-blue-600 text-white font-bold rounded-xl disabled:opacity-50 disabled:cursor-not-allowed hover:opacity-90 transition-opacity"
              >
                Continue to Face Capture
              </button>
            </div>

            {error && (
              <div className="mt-4 p-4 bg-red-500/20 border border-red-500 rounded-xl text-red-200">
                {error}
              </div>
            )}
          </div>
        </div>
      </Shell>
    );
  }

  // Face capture step
  if (step === ENROLLMENT_STEPS.FACE) {
    return (
      <Shell>
        <div className="max-w-2xl mx-auto">
          <div className="glass-panel rounded-[28px] p-8">
            <h1 className="text-2xl font-bold text-white text-center mb-2">
              Face Enrollment
            </h1>
            <p className="text-slate-300 text-center mb-6">
              Capture 5 face samples from slightly different angles
            </p>
            
            {/* Progress */}
            <div className="mb-6">
              <div className="flex justify-between text-sm text-slate-400 mb-2">
                <span>Progress</span>
                <span>{faceSamples.length}/5 samples</span>
              </div>
              <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
                <div 
                  className="h-full bg-gradient-to-r from-cyan-400 to-blue-500 transition-all duration-500"
                  style={{ width: `${(faceSamples.length / 5) * 100}%` }}
                />
              </div>
            </div>

            {/* Camera Preview */}
            <div className="relative mb-6 rounded-2xl overflow-hidden bg-slate-900">
              <video
                ref={videoRef}
                autoPlay
                playsInline
                muted
                className="w-full aspect-video object-cover"
              />
              
              {/* Face Guide Overlay */}
              <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                <div className="w-48 h-64 border-2 border-dashed border-cyan-400/50 rounded-3xl flex items-center justify-center">
                  <span className="text-cyan-400/70 text-sm">Position face here</span>
                </div>
              </div>
              
              {/* Sample indicators */}
              <div className="absolute top-4 right-4 flex gap-2">
                {[0, 1, 2, 3, 4].map((i) => (
                  <div
                    key={i}
                    className={`w-3 h-3 rounded-full ${
                      i < faceSamples.length ? "bg-green-500" : "bg-slate-600"
                    }`}
                  />
                ))}
              </div>
            </div>

            <button
              onClick={captureFaceSample}
              disabled={faceSamples.length >= 5}
              className="w-full py-4 px-6 bg-gradient-to-r from-cyan-500 to-blue-600 text-white font-bold rounded-xl disabled:opacity-50 hover:opacity-90 transition-opacity"
            >
              {faceSamples.length >= 5 ? "Face Capture Complete" : "📸 Capture Face Sample"}
            </button>
          </div>
        </div>
      </Shell>
    );
  }

  // Voice capture step
  if (step === ENROLLMENT_STEPS.VOICE) {
    return (
      <Shell>
        <div className="max-w-2xl mx-auto">
          <div className="glass-panel rounded-[28px] p-8">
            <h1 className="text-2xl font-bold text-white text-center mb-2">
              Voice Enrollment
            </h1>
            <p className="text-slate-300 text-center mb-6">
              Record 4 voice samples by reading the phrase below
            </p>
            
            {/* Progress */}
            <div className="mb-6">
              <div className="flex justify-between text-sm text-slate-400 mb-2">
                <span>Progress</span>
                <span>{voiceSamples.length}/4 samples</span>
              </div>
              <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
                <div 
                  className="h-full bg-gradient-to-r from-cyan-400 to-blue-500 transition-all duration-500"
                  style={{ width: `${(voiceSamples.length / 4) * 100}%` }}
                />
              </div>
            </div>

            {/* Phrase Card */}
            <div className="bg-slate-800/50 rounded-xl p-6 mb-6 text-center">
              <p className="text-slate-400 text-sm mb-2">Please read this phrase:</p>
              <p className="text-xl text-white font-medium leading-relaxed">
                "The quick brown fox jumps over the lazy dog. 
                Artificial intelligence is transforming how we conduct technical interviews."
              </p>
            </div>

            {/* Recording Indicator */}
            {mediaRecorderRef.current?.state === "recording" && (
              <div className="flex items-center justify-center gap-2 mb-6 text-red-400 animate-pulse">
                <div className="w-3 h-3 bg-red-500 rounded-full" />
                <span>Recording...</span>
              </div>
            )}

            {/* Sample indicators */}
            <div className="flex justify-center gap-2 mb-6">
              {[0, 1, 2, 3].map((i) => (
                <div
                  key={i}
                  className={`w-12 h-12 rounded-xl flex items-center justify-center ${
                    i < voiceSamples.length 
                      ? "bg-green-500/20 border border-green-500 text-green-400" 
                      : "bg-slate-700 text-slate-500"
                  }`}
                >
                  {i < voiceSamples.length ? "✓" : i + 1}
                </div>
              ))}
            </div>

            <button
              onClick={startVoiceRecording}
              disabled={
                voiceSamples.length >= 4 || 
                mediaRecorderRef.current?.state === "recording"
              }
              className="w-full py-4 px-6 bg-gradient-to-r from-cyan-500 to-blue-600 text-white font-bold rounded-xl disabled:opacity-50 hover:opacity-90 transition-opacity"
            >
              {voiceSamples.length >= 4 
                ? "Voice Capture Complete" 
                : "🎙️ Start Voice Recording (5 sec)"
              }
            </button>
          </div>
        </div>
      </Shell>
    );
  }

  // Complete step
  if (step === ENROLLMENT_STEPS.COMPLETE) {
    return (
      <Shell>
        <div className="max-w-2xl mx-auto">
          <div className="glass-panel rounded-[28px] p-8 text-center">
            <div className="w-24 h-24 mx-auto bg-green-500/20 rounded-full flex items-center justify-center mb-6">
              <span className="text-5xl">✓</span>
            </div>
            
            <h1 className="text-3xl font-bold text-white mb-4">
              Enrollment Complete!
            </h1>
            <p className="text-slate-300 mb-8">
              Your biometric data has been captured successfully. 
              You are now ready to start the interview.
            </p>

            <div className="grid grid-cols-2 gap-4 mb-8">
              <div className="bg-slate-800/50 rounded-xl p-4">
                <div className="text-3xl mb-2">👤</div>
                <div className="text-white font-semibold">{faceSamples.length} Face Samples</div>
                <div className="text-slate-400 text-sm">Face verification ready</div>
              </div>
              <div className="bg-slate-800/50 rounded-xl p-4">
                <div className="text-3xl mb-2">🎙️</div>
                <div className="text-white font-semibold">{voiceSamples.length} Voice Samples</div>
                <div className="text-slate-400 text-sm">Voice matching ready</div>
              </div>
            </div>

            <button
              onClick={submitEnrollment}
              disabled={isProcessing}
              className="w-full py-4 px-6 bg-gradient-to-r from-green-500 to-emerald-600 text-white font-bold rounded-xl disabled:opacity-50 hover:opacity-90 transition-opacity"
            >
              {isProcessing ? "Processing..." : "Start Interview →"}
            </button>

            {error && (
              <div className="mt-4 p-4 bg-red-500/20 border border-red-500 rounded-xl text-red-200">
                {error}
              </div>
            )}
          </div>
        </div>
      </Shell>
    );
  }

  return null;
}
