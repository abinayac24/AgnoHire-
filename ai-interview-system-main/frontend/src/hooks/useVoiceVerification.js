import { useCallback, useEffect, useRef, useState } from "react";

export function useVoiceVerification(sessionId, onVoiceMismatch) {
  const [isEnrolled, setIsEnrolled] = useState(false);
  const [verificationStatus, setVerificationStatus] = useState("idle");
  const [similarityScore, setSimilarityScore] = useState(null);
  const [warningLevel, setWarningLevel] = useState("none");
  const [verificationHistory, setVerificationHistory] = useState([]);
  
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const verificationIntervalRef = useRef(null);
  
  // Check enrollment status
  const checkEnrollmentStatus = useCallback(async () => {
    try {
      const response = await fetch(`${import.meta.env.VITE_API_URL || "http://localhost:8000"}/api/voice/status/${sessionId}`);
      if (!response.ok) throw new Error("Failed to check voice status");
      
      const data = await response.json();
      setIsEnrolled(data.enrolled);
      
      console.info(`[VoiceVerification] Enrollment status: ${data.enrolled}`);
      return data.enrolled;
    } catch (err) {
      console.error("[VoiceVerification] Status check failed:", err);
      return false;
    }
  }, [sessionId]);

  // Start continuous voice verification
  const startVoiceVerification = useCallback(async () => {
    if (!sessionId) return;
    
    // Check if voice is enrolled
    const enrolled = await checkEnrollmentStatus();
    if (!enrolled) {
      console.warn("[VoiceVerification] No voice enrollment found");
      return;
    }
    
    console.info("[VoiceVerification] Starting continuous verification");
    
    try {
      // Get microphone access
      const stream = await navigator.mediaDevices.getUserMedia({ 
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          sampleRate: 16000
        } 
      });
      
      // Setup media recorder
      const mediaRecorder = new MediaRecorder(stream, {
        mimeType: 'audio/webm;codecs=opus'
      });
      
      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];
      
      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };
      
      mediaRecorder.onstop = async () => {
        if (audioChunksRef.current.length > 0) {
          const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
          await verifyVoiceSample(audioBlob);
          audioChunksRef.current = [];
        }
      };
      
      // Start recording in 5-second chunks
      const startRecordingCycle = () => {
        if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'inactive') {
          mediaRecorderRef.current.start();
          
          // Stop after 5 seconds
          setTimeout(() => {
            if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
              mediaRecorderRef.current.stop();
            }
          }, 5000);
        }
      };
      
      // Start first recording
      startRecordingCycle();
      
      // Continue recording every 10 seconds
      verificationIntervalRef.current = setInterval(startRecordingCycle, 10000);
      
      setVerificationStatus("active");
      console.info("[VoiceVerification] Continuous verification started");
      
    } catch (err) {
      console.error("[VoiceVerification] Failed to start:", err);
      setVerificationStatus("error");
    }
  }, [sessionId, checkEnrollmentStatus]);

  // Stop voice verification
  const stopVoiceVerification = useCallback(() => {
    if (verificationIntervalRef.current) {
      clearInterval(verificationIntervalRef.current);
      verificationIntervalRef.current = null;
    }
    
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
    }
    
    if (mediaRecorderRef.current?.stream) {
      mediaRecorderRef.current.stream.getTracks().forEach(track => track.stop());
    }
    
    setVerificationStatus("idle");
    console.info("[VoiceVerification] Verification stopped");
  }, []);

  // Verify voice sample
  const verifyVoiceSample = useCallback(async (audioBlob) => {
    try {
      setVerificationStatus("verifying");
      
      // Convert to base64
      const reader = new FileReader();
      const audioBase64 = await new Promise((resolve) => {
        reader.onloadend = () => resolve(reader.result);
        reader.readAsDataURL(audioBlob);
      });
      
      // Send to backend
      const response = await fetch(`${import.meta.env.VITE_API_URL || "http://localhost:8000"}/api/voice/verify`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          audio_data: audioBase64,
          timestamp: Date.now() / 1000
        })
      });
      
      if (!response.ok) throw new Error("Verification failed");
      
      const result = await response.json();
      
      // Update state
      setSimilarityScore(result.similarity_score);
      setWarningLevel(result.warning_level);
      
      // Add to history
      setVerificationHistory(prev => [...prev.slice(-9), {
        timestamp: Date.now(),
        verified: result.verified,
        similarity: result.similarity_score,
        warning: result.warning_level
      }]);
      
      console.info(`[VoiceVerification] Result: verified=${result.verified}, similarity=${result.similarity_score.toFixed(3)}, level=${result.warning_level}`);
      
      // Handle mismatch
      if (result.should_alert && onVoiceMismatch) {
        console.warn("[VoiceVerification] Voice mismatch detected!");
        onVoiceMismatch(result);
      }
      
      setVerificationStatus("active");
      
    } catch (err) {
      console.error("[VoiceVerification] Sample verification failed:", err);
      setVerificationStatus("error");
    }
  }, [sessionId, onVoiceMismatch]);

  // Enroll voice (for testing/setup)
  const enrollVoice = useCallback(async (audioSamples) => {
    try {
      console.info("[VoiceVerification] Starting voice enrollment");
      
      const response = await fetch(`${import.meta.env.VITE_API_URL || "http://localhost:8000"}/api/voice/enroll`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          username: "candidate",
          audio_samples: audioSamples,
          sample_duration: 5.0
        })
      });
      
      if (!response.ok) throw new Error("Enrollment failed");
      
      const result = await response.json();
      setIsEnrolled(true);
      
      console.info("[VoiceVerification] Enrollment successful:", result);
      return result;
      
    } catch (err) {
      console.error("[VoiceVerification] Enrollment failed:", err);
      throw err;
    }
  }, [sessionId]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopVoiceVerification();
    };
  }, [stopVoiceVerification]);

  return {
    // State
    isEnrolled,
    verificationStatus,
    similarityScore,
    warningLevel,
    verificationHistory,
    
    // Actions
    startVoiceVerification,
    stopVoiceVerification,
    verifyVoiceSample,
    enrollVoice,
    checkEnrollmentStatus
  };
}
