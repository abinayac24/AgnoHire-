// Voice Recognition Diagnostic and Fix System
// Use this in browser console to diagnose and fix voice recognition issues

// Test 1: Comprehensive microphone and audio system check
function diagnoseMicrophoneAndAudioSystem() {
  console.warn("[MICROPHONE DIAGNOSTIC] ==============================================");
  console.warn("[MICROPHONE DIAGNOSTIC] COMPREHENSIVE MICROPHONE AND AUDIO SYSTEM CHECK");
  console.warn("[MICROPHONE DIAGNOSTIC] ==============================================");
  
  // Check browser audio support
  console.warn("[MICROPHONE DIAGNOSTIC] Checking browser audio support...");
  const audioContextSupported = window.AudioContext || window.webkitAudioContext;
  const getUserMediaSupported = navigator.mediaDevices && navigator.mediaDevices.getUserMedia;
  const speechRecognitionSupported = window.SpeechRecognition || window.webkitSpeechRecognition;
  
  console.warn("[MICROPHONE DIAGNOSTIC] Audio support:");
  console.warn("[MICROPHONE DIAGNOSTIC]   AudioContext:", !!audioContextSupported);
  console.warn("[MICROPHONE DIAGNOSTIC]   getUserMedia:", !!getUserMediaSupported);
  console.warn("[MICROPHONE DIAGNOSTIC]   SpeechRecognition:", !!speechRecognitionSupported);
  
  if (!audioContextSupported || !getUserMediaSupported || !speechRecognitionSupported) {
    console.error("[MICROPHONE DIAGNOSTIC] ❌ CRITICAL: Browser does not support required audio APIs");
    return false;
  }
  
  // Check microphone permissions
  console.warn("[MICROPHONE DIAGNOSTIC] Checking microphone permissions...");
  navigator.permissions.query({ name: 'microphone' })
    .then(permissionStatus => {
      console.warn("[MICROPHONE DIAGNOSTIC] Microphone permission state:", permissionStatus.state);
      if (permissionStatus.state === 'denied') {
        console.error("[MICROPHONE DIAGNOSTIC] ❌ Microphone permission denied");
      } else if (permissionStatus.state === 'prompt') {
        console.warn("[MICROPHONE DIAGNOSTIC] ⚠️ Microphone permission prompt required");
      } else {
        console.warn("[MICROPHONE DIAGNOSTIC] ✅ Microphone permission granted");
      }
    })
    .catch(error => {
      console.error("[MICROPHONE DIAGNOSTIC] ❌ Error checking microphone permissions:", error);
    });
  
  // Test microphone access
  console.warn("[MICROPHONE DIAGNOSTIC] Testing microphone access...");
  navigator.mediaDevices.getUserMedia({ audio: true, video: false })
    .then(stream => {
      console.warn("[MICROPHONE DIAGNOSTIC] ✅ Microphone access granted");
      console.warn("[MICROPHONE DIAGNOSTIC] Stream details:");
      console.warn("[MICROPHONE DIAGNOSTIC]   Active:", stream.active);
      console.warn("[MICROPHONE DIAGNOSTIC]   Audio tracks:", stream.getAudioTracks().length);
      
      // Test audio levels
      const audioContext = new (window.AudioContext || window.webkitAudioContext)();
      const analyser = audioContext.createAnalyser();
      const source = audioContext.createMediaStreamSource(stream);
      source.connect(analyser);
      
      const testAudioLevels = () => {
        const dataArray = new Uint8Array(analyser.frequencyBinCount);
        analyser.getByteFrequencyData(dataArray);
        
        // Calculate average audio level
        let sum = 0;
        for (let i = 0; i < dataArray.length; i++) {
          sum += dataArray[i];
        }
        const average = sum / dataArray.length;
        const normalizedLevel = average / 255;
        
        if (normalizedLevel > 0.01) {
          console.warn(`[MICROPHONE DIAGNOSTIC] ✅ Audio level detected: ${(normalizedLevel * 100).toFixed(1)}%`);
        } else {
          console.warn("[MICROPHONE DIAGNOSTIC] ⚠️ Low audio level detected");
        }
      };
      
      // Test audio levels for 3 seconds
      let testCount = 0;
      const audioTestInterval = setInterval(() => {
        testAudioLevels();
        testCount++;
        if (testCount >= 30) { // 3 seconds at 100ms intervals
          clearInterval(audioTestInterval);
          stream.getTracks().forEach(track => track.stop());
          console.warn("[MICROPHONE DIAGNOSTIC] ✅ Microphone test completed");
        }
      }, 100);
      
    })
    .catch(error => {
      console.error("[MICROPHONE DIAGNOSTIC] ❌ Microphone access failed:", error);
      console.error("[MICROPHONE DIAGNOSTIC] Error name:", error.name);
      console.error("[MICROPHONE DIAGNOSTIC] Error message:", error.message);
    });
  
  console.warn("[MICROPHONE DIAGNOSTIC] ==============================================");
  console.warn("[MICROPHONE DIAGNOSTIC] MICROPHONE AND AUDIO SYSTEM CHECK COMPLETED");
  console.warn("[MICROPHONE DIAGNOSTIC] ==============================================");
}

// Test 2: Check STT service connectivity and configuration
function diagnoseSTTService() {
  console.warn("[STT DIAGNOSTIC] ==============================================");
  console.warn("[STT DIAGNOSTIC] CHECKING STT SERVICE CONNECTIVITY");
  console.warn("[STT DIAGNOSTIC] ==============================================");
  
  // Check STT endpoint configuration
  console.warn("[STT DIAGNOSTIC] STT service configuration:");
  console.warn("[STT DIAGNOSTIC]   Endpoint:", speechTranscribeEndpoint);
  console.warn("[STT DIAGNOSTIC]   Method: POST");
  console.warn("[STT DIAGNOSTIC]   Expected format: multipart/form-data");
  
  // Test STT service health
  console.warn("[STT DIAGNOSTIC] Testing STT service health...");
  
  // Test with a small audio blob
  const testSTTService = async () => {
    try {
      const testFormData = new FormData();
      testFormData.append("audio", new Blob(["test audio data"], { type: "audio/webm" }));
      testFormData.append("context_question", "test question");
      
      const response = await fetch(speechTranscribeEndpoint, {
        method: "POST",
        body: testFormData,
        signal: AbortSignal.timeout(5000) // 5 second timeout
      });
      
      if (response.ok) {
        console.warn("[STT DIAGNOSTIC] ✅ STT service responding");
        console.warn("[STT DIAGNOSTIC]   Status:", response.status);
        return true;
      } else {
        console.error("[STT DIAGNOSTIC] ❌ STT service error:", response.status);
        console.error("[STT DIAGNOSTIC]   Status text:", response.statusText);
        return false;
      }
    } catch (error) {
      console.error("[STT DIAGNOSTIC] ❌ STT service connection error:", error);
      return false;
    }
  };
  
  // Run test
  testSTTService().then(success => {
    if (success) {
      console.warn("[STT DIAGNOSTIC] ✅ STT service is accessible and responding");
    } else {
      console.error("[STT DIAGNOSTIC] ❌ STT service is not accessible");
    }
  });
  
  console.warn("[STT DIAGNOSTIC] ==============================================");
  console.warn("[STT DIAGNOSTIC] STT SERVICE CHECK COMPLETED");
  console.warn("[STT DIAGNOSTIC] ==============================================");
}

// Test 3: Check VAD (Voice Activity Detection) configuration
function diagnoseVADSystem() {
  console.warn("[VAD DIAGNOSTIC] ==============================================");
  console.warn("[VAD DIAGNOSTIC] CHECKING VOICE ACTIVITY DETECTION SYSTEM");
  console.warn("[VAD DIAGNOSTIC] ==============================================");
  
  // Check VAD configuration
  console.warn("[VAD DIAGNOSTIC] VAD configuration:");
  console.warn("[VAD DIAGNOSTIC]   VAD_SPEECH_THRESHOLD:", VAD_SPEECH_THRESHOLD);
  console.warn("[VAD DIAGNOSTIC]   VAD_POLL_MS:", VAD_POLL_MS);
  console.warn("[VAD DIAGNOSTIC]   MIN_SEGMENT_MS:", MIN_SEGMENT_MS);
  console.warn("[VAD DIAGNOSTIC]   SPEECH_SILENCE_MS:", SPEECH_SILENCE_MS);
  
  // Test if VAD is too sensitive or not sensitive enough
  if (VAD_SPEECH_THRESHOLD < 0.01) {
    console.warn("[VAD DIAGNOSTIC] ⚠️ VAD threshold might be too low (very sensitive):", VAD_SPEECH_THRESHOLD);
    console.warn("[VAD DIAGNOSTIC]   Consider increasing to 0.015-0.025 for normal speech");
  } else if (VAD_SPEECH_THRESHOLD > 0.05) {
    console.warn("[VAD DIAGNOSTIC] ⚠️ VAD threshold might be too high (not sensitive):", VAD_SPEECH_THRESHOLD);
    console.warn("[VAD DIAGNOSTIC]   Consider decreasing to 0.015-0.025 for normal speech");
  } else {
    console.warn("[VAD DIAGNOSTIC] ✅ VAD threshold appears reasonable:", VAD_SPEECH_THRESHOLD);
  }
  
  // Check VAD polling frequency
  if (VAD_POLL_MS < 50) {
    console.warn("[VAD DIAGNOSTIC] ⚠️ VAD polling might be too frequent (< 50ms):", VAD_POLL_MS);
  } else if (VAD_POLL_MS > 200) {
    console.warn("[VAD DIAGNOSTIC] ⚠️ VAD polling might be too slow (> 200ms):", VAD_POLL_MS);
  } else {
    console.warn("[VAD DIAGNOSTIC] ✅ VAD polling frequency appears reasonable:", VAD_POLL_MS);
  }
  
  console.warn("[VAD DIAGNOSTIC] ==============================================");
  console.warn("[VAD DIAGNOSTIC] VAD SYSTEM CHECK COMPLETED");
  console.warn("[VAD DIAGNOSTIC] ==============================================");
}

// Test 4: Check browser speech recognition system
function diagnoseBrowserSpeechRecognition() {
  console.warn("[BROWSER STT DIAGNOSTIC] ==============================================");
  console.warn("[BROWSER STT DIAGNOSTIC] CHECKING BROWSER SPEECH RECOGNITION");
  console.warn("[BROWSER STT DIAGNOSTIC] ==============================================");
  
  // Check browser speech recognition support
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  
  if (!SpeechRecognition) {
    console.error("[BROWSER STT DIAGNOSTIC] ❌ Browser speech recognition not supported");
    return false;
  }
  
  console.warn("[BROWSER STT DIAGNOSTIC] ✅ Browser speech recognition supported");
  
  // Test browser speech recognition
  try {
    const testRecognition = new SpeechRecognition();
    
    // Configure for optimal performance
    testRecognition.continuous = false;
    testRecognition.interimResults = true;
    testRecognition.lang = 'en-US';
    testRecognition.maxAlternatives = 3;
    
    console.warn("[BROWSER STT DIAGNOSTIC] Browser STT configuration:");
    console.warn("[BROWSER STT DIAGNOSTIC]   Continuous:", testRecognition.continuous);
    console.warn("[BROWSER STT DIAGNOSTIC]   Interim results:", testRecognition.interimResults);
    console.warn("[BROWSER STT DIAGNOSTIC]   Language:", testRecognition.lang);
    console.warn("[BROWSER STT DIAGNOSTIC]   Max alternatives:", testRecognition.maxAlternatives);
    
    // Test recognition
    let recognitionStarted = false;
    let resultsReceived = false;
    
    testRecognition.onstart = () => {
      console.warn("[BROWSER STT DIAGNOSTIC] ✅ Browser STT started");
      recognitionStarted = true;
    };
    
    testRecognition.onresult = (event) => {
      if (event.results && event.results.length > 0) {
        const result = event.results[event.results.length - 1];
        if (result.isFinal) {
          console.warn("[BROWSER STT DIAGNOSTIC] ✅ Browser STT result received:", result[0].transcript);
          resultsReceived = true;
        }
      }
    };
    
    testRecognition.onerror = (event) => {
      console.error("[BROWSER STT DIAGNOSTIC] ❌ Browser STT error:", event.error);
    };
    
    testRecognition.onend = () => {
      console.warn("[BROWSER STT DIAGNOSTIC] Browser STT ended");
      if (recognitionStarted && !resultsReceived) {
        console.warn("[BROWSER STT DIAGNOSTIC] ⚠️ No speech recognized during test");
      } else {
        console.warn("[BROWSER STT DIAGNOSTIC] ✅ Browser STT working correctly");
      }
    };
    
    // Start test
    testRecognition.start();
    
    // Stop test after 5 seconds
    setTimeout(() => {
      testRecognition.stop();
    }, 5000);
    
  } catch (error) {
    console.error("[BROWSER STT DIAGNOSTIC] ❌ Browser STT test failed:", error);
  }
  
  console.warn("[BROWSER STT DIAGNOSTIC] ==============================================");
  console.warn("[BROWSER STT DIAGNOSTIC] BROWSER STT CHECK COMPLETED");
  console.warn("[BROWSER STT DIAGNOSTIC] ==============================================");
}

// Test 5: Check current interview voice recognition state
function diagnoseCurrentVoiceRecognitionState() {
  console.warn("[CURRENT STATE DIAGNOSTIC] ==============================================");
  console.warn("[CURRENT STATE DIAGNOSTIC] CHECKING CURRENT VOICE RECOGNITION STATE");
  console.warn("[CURRENT STATE DIAGNOSTIC] ==============================================");
  
  // Check current voice recognition variables
  console.warn("[CURRENT STATE DIAGNOSTIC] Current voice recognition state:");
  console.warn("[CURRENT STATE DIAGNOSTIC]   isRecording:", isRecording);
  console.warn("[CURRENT STATE DIAGNOSTIC]   isTranscribing:", isTranscribing);
  console.warn("[CURRENT STATE DIAGNOSTIC]   recognitionActive:", recognitionActive);
  console.warn("[CURRENT STATE DIAGNOSTIC]   micStream exists:", !!micStream);
  console.warn("[CURRENT STATE DIAGNOSTIC]   micStream active:", !!(micStream && micStream.active));
  console.warn("[CURRENT STATE DIAGNOSTIC]   speechRecognition exists:", !!speechRecognition);
  console.warn("[CURRENT STATE DIAGNOSTIC]   audioContext exists:", !!audioContext);
  console.warn("[CURRENT STATE DIAGNOSTIC]   audioAnalyser exists:", !!audioAnalyser);
  
  // Check current settings
  console.warn("[CURRENT STATE DIAGNOSTIC] Current voice recognition settings:");
  console.warn("[CURRENT STATE DIAGNOSTIC]   VAD_SPEECH_THRESHOLD:", VAD_SPEECH_THRESHOLD);
  console.warn("[CURRENT STATE DIAGNOSTIC]   STT_CONFIDENCE_THRESHOLD:", STT_CONFIDENCE_THRESHOLD);
  console.warn("[CURRENT STATE DIAGNOSTIC]   AUDIO_BUFFER_MS:", AUDIO_BUFFER_MS);
  console.warn("[CURRENT STATE DIAGNOSTIC]   SPEECH_SILENCE_MS:", SPEECH_SILENCE_MS);
  
  // Check if voice recognition is properly initialized
  if (!isRecording && !isTranscribing && !recognitionActive) {
    console.warn("[CURRENT STATE DIAGNOSTIC] ⚠️ Voice recognition appears to be inactive");
  } else if (isRecording && isTranscribing && recognitionActive) {
    console.warn("[CURRENT STATE DIAGNOSTIC] ✅ Voice recognition appears to be active");
  } else {
    console.warn("[CURRENT STATE DIAGNOSTIC] ⚠️ Voice recognition state unclear");
  }
  
  console.warn("[CURRENT STATE DIAGNOSTIC] ==============================================");
  console.warn("[CURRENT STATE DIAGNOSTIC] CURRENT STATE CHECK COMPLETED");
  console.warn("[CURRENT STATE DIAGNOSTIC] ==============================================");
}

// Test 6: Apply fixes for common voice recognition issues
function applyVoiceRecognitionFixes() {
  console.warn("[VOICE FIXES] ==============================================");
  console.warn("[VOICE FIXES] APPLYING VOICE RECOGNITION FIXES");
  console.warn("[VOICE FIXES] ==============================================");
  
  // Fix 1: Ensure microphone permissions are properly requested
  console.warn("[VOICE FIXES] Fix 1: Ensuring microphone permissions...");
  if (navigator.permissions && navigator.permissions.query) {
    navigator.permissions.query({ name: 'microphone' })
      .then(permissionStatus => {
        if (permissionStatus.state === 'denied') {
          console.warn("[VOICE FIXES] Requesting microphone permission...");
          navigator.permissions.request({ name: 'microphone' })
            .then(() => {
              console.warn("[VOICE FIXES] ✅ Microphone permission requested");
            })
            .catch(error => {
              console.error("[VOICE FIXES] ❌ Failed to request microphone permission:", error);
            });
        }
      })
      .catch(error => {
        console.error("[VOICE FIXES] ❌ Error checking permissions:", error);
      });
  }
  
  // Fix 2: Optimize VAD threshold for better sensitivity
  console.warn("[VOICE FIXES] Fix 2: Optimizing VAD threshold...");
  if (VAD_SPEECH_THRESHOLD < 0.015) {
    console.warn("[VOICE FIXES] Increasing VAD threshold from", VAD_SPEECH_THRESHOLD, "to 0.018 for better sensitivity");
    window.VAD_SPEECH_THRESHOLD = 0.018;
  } else if (VAD_SPEECH_THRESHOLD > 0.035) {
    console.warn("[VOICE FIXES] Decreasing VAD threshold from", VAD_SPEECH_THRESHOLD, "to 0.025 for better sensitivity");
    window.VAD_SPEECH_THRESHOLD = 0.025;
  }
  
  // Fix 3: Ensure proper audio context setup
  console.warn("[VOICE FIXES] Fix 3: Ensuring proper audio context...");
  if (!audioContext && micStream) {
    console.warn("[VOICE FIXES] Reinitializing audio context with microphone stream...");
    try {
      // Force reconnection of audio analyser
      const newAudioContext = new (window.AudioContext || window.webkitAudioContext)();
      const newAnalyser = newAudioContext.createAnalyser();
      const source = newAudioContext.createMediaStreamSource(micStream);
      source.connect(newAnalyser);
      
      // Update global references
      window.audioContext = newAudioContext;
      window.audioAnalyser = newAnalyser;
      
      console.warn("[VOICE FIXES] ✅ Audio context reinitialized with microphone stream");
    } catch (error) {
      console.error("[VOICE FIXES] ❌ Failed to reinitialize audio context:", error);
    }
  }
  
  // Fix 4: Restart voice recognition if needed
  console.warn("[VOICE FIXES] Fix 4: Restarting voice recognition if needed...");
  if (!isRecording && interviewStarted && !isTranscribing) {
    console.warn("[VOICE FIXES] Restarting hands-free listening...");
    setTimeout(() => {
      startHandsFreeListening();
    }, 1000);
  }
  
  // Fix 5: Clear any stuck states
  console.warn("[VOICE FIXES] Fix 5: Clearing stuck states...");
  if (isTranscribing && !micStream) {
    console.warn("[VOICE FIXES] Clearing stuck transcribing state");
    window.isTranscribing = false;
  }
  
  if (recognitionActive && !speechRecognition) {
    console.warn("[VOICE FIXES] Clearing stuck recognition state");
    window.recognitionActive = false;
  }
  
  console.warn("[VOICE FIXES] ==============================================");
  console.warn("[VOICE FIXES] VOICE RECOGNITION FIXES APPLIED");
  console.warn("[VOICE FIXES] ==============================================");
}

// Test 7: Run complete voice recognition diagnostic and fix
function runCompleteVoiceRecognitionDiagnostic() {
  console.warn("[COMPLETE VOICE DIAGNOSTIC] ==============================================");
  console.warn("[COMPLETE VOICE DIAGNOSTIC] RUNNING COMPLETE VOICE RECOGNITION DIAGNOSTIC AND FIX");
  console.warn("[COMPLETE VOICE DIAGNOSTIC] ==============================================");
  
  // Run all diagnostics in sequence
  diagnoseMicrophoneAndAudioSystem();
  
  setTimeout(() => {
    diagnoseSTTService();
  }, 2000);
  
  setTimeout(() => {
    diagnoseVADSystem();
  }, 4000);
  
  setTimeout(() => {
    diagnoseBrowserSpeechRecognition();
  }, 6000);
  
  setTimeout(() => {
    diagnoseCurrentVoiceRecognitionState();
  }, 8000);
  
  setTimeout(() => {
    applyVoiceRecognitionFixes();
  }, 10000);
  
  setTimeout(() => {
    console.warn("[COMPLETE VOICE DIAGNOSTIC] ==============================================");
    console.warn("[COMPLETE VOICE DIAGNOSTIC] ALL DIAGNOSTICS AND FIXES COMPLETED");
    console.warn("[COMPLETE VOICE DIAGNOSTIC] Check console for issues and fixes applied");
    console.warn("[COMPLETE VOICE DIAGNOSTIC] ==============================================");
  }, 12000);
  
  console.warn("[COMPLETE VOICE DIAGNOSTIC] Complete diagnostic started. Check console for detailed results.");
}

console.warn("[VOICE RECOGNITION DIAGNOSTIC] Voice recognition diagnostic functions loaded:");
console.warn("[VOICE RECOGNITION DIAGNOSTIC] - diagnoseMicrophoneAndAudioSystem()");
console.warn("[VOICE RECOGNITION DIAGNOSTIC] - diagnoseSTTService()");
console.warn("[VOICE RECOGNITION DIAGNOSTIC] - diagnoseVADSystem()");
console.warn("[VOICE RECOGNITION DIAGNOSTIC] - diagnoseBrowserSpeechRecognition()");
console.warn("[VOICE RECOGNITION DIAGNOSTIC] - diagnoseCurrentVoiceRecognitionState()");
console.warn("[VOICE RECOGNITION DIAGNOSTIC] - applyVoiceRecognitionFixes()");
console.warn("[VOICE RECOGNITION DIAGNOSTIC] - runCompleteVoiceRecognitionDiagnostic()");
console.warn("");
console.warn("[VOICE RECOGNITION DIAGNOSTIC] Run diagnostic to identify and fix voice recognition issues:");
console.warn("[VOICE RECOGNITION DIAGNOSTIC]   runCompleteVoiceRecognitionDiagnostic()");
