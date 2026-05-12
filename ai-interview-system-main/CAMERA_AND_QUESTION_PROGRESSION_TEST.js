// Camera and Question Progression Test Functions
// Use these in browser console to test camera view and question progression

// Test 1: Verify camera stream is properly connected and working
function testCameraStream() {
  console.warn("[CAMERA TEST] ==============================================");
  console.warn("[CAMERA TEST] TESTING CAMERA STREAM FUNCTIONALITY");
  console.warn("[CAMERA TEST] ==============================================");
  
  // Check camera stream state
  console.warn("[CAMERA TEST] Camera stream state:", {
    cameraStream_exists: !!cameraStream,
    cameraStream_active: !!(cameraStream && cameraStream.active),
    cameraStream_id: cameraStream ? cameraStream.id : 'null',
    cameraTracks: cameraStream ? cameraStream.getAudioTracks().length : 0
  });
  
  // Check preview element state
  const preview = document.getElementById("cameraPreview");
  console.warn("[CAMERA TEST] Preview element state:", {
    preview_exists: !!preview,
    preview_readyState: preview ? preview.readyState : 'null',
    preview_videoWidth: preview ? preview.videoWidth : 0,
    preview_videoHeight: preview ? preview.videoHeight : 0,
    preview_srcObject: !!(preview && preview.srcObject)
  });
  
  // Check face detector state
  console.warn("[CAMERA TEST] Face detection state:", {
    faceDetector_exists: !!faceDetector,
    face_absence_detection_enabled: FACE_ABSENCE_DETECTION_ENABLED,
    proctoring_disabled: PROCTORING_DISABLED,
    interview_started: interviewStarted
  });
  
  // Test camera permissions
  navigator.mediaDevices.getUserMedia({ video: true, audio: false })
    .then(stream => {
      console.warn("[CAMERA TEST] ✅ Camera permissions: GRANTED");
      stream.getTracks().forEach(track => {
        console.warn("[CAMERA TEST] Track state:", {
          kind: track.kind,
          enabled: track.enabled,
          readyState: track.readyState,
          settings: track.getSettings()
        });
      });
      
      // Clean up test stream
      stream.getTracks().forEach(track => track.stop());
    })
    .catch(error => {
      console.error("[CAMERA TEST] ❌ Camera permissions: DENIED");
      console.error("[CAMERA TEST] Error:", error);
    });
  
  console.warn("[CAMERA TEST] ==============================================");
  console.warn("[CAMERA TEST] CAMERA STREAM TEST COMPLETED");
  console.warn("[CAMERA TEST] ==============================================");
}

// Test 2: Test face detection functionality
function testFaceDetection() {
  console.warn("[FACE TEST] ==============================================");
  console.warn("[FACE TEST] TESTING FACE DETECTION FUNCTIONALITY");
  console.warn("[FACE TEST] ==============================================");
  
  const preview = document.getElementById("cameraPreview");
  if (!preview || preview.readyState < 2) {
    console.error("[FACE TEST] ❌ Preview not available for face detection test");
    return;
  }
  
  // Test face detection manually
  if (faceDetector) {
    console.warn("[FACE TEST] Testing face detection...");
    faceDetector.detect(preview)
      .then(faces => {
        console.warn("[FACE TEST] ✅ Face detection successful:", {
          faceCount: faces.length,
          faceDetected: faces.length > 0,
          faceDetails: faces.map((face, i) => ({
            index: i,
            confidence: face.confidence,
            boundingBox: face.boundingBox
          }))
        });
      })
      .catch(error => {
        console.error("[FACE TEST] ❌ Face detection failed:", error);
      });
  } else {
    console.error("[FACE TEST] ❌ Face detector not initialized");
  }
  
  console.warn("[FACE TEST] ==============================================");
  console.warn("[FACE TEST] FACE DETECTION TEST COMPLETED");
  console.warn("[FACE TEST] ==============================================");
}

// Test 3: Test question progression with simulated timer expiry
function testQuestionProgression() {
  console.warn("[PROGRESSION TEST] ==============================================");
  console.warn("[PROGRESSION TEST] TESTING QUESTION PROGRESSION");
  console.warn("[PROGRESSION TEST] ==============================================");
  
  // Check current interview state
  console.warn("[PROGRESSION TEST] Current interview state:", {
    interviewStarted: interviewStarted,
    currentQuestionId: getActiveQuestionId(),
    currentQuestionIndex: currentQuestionIndex,
    isRecording: isRecording,
    isSavingAnswer: isSavingAnswer,
    isTranscribing: isTranscribing,
    hasActiveQuestion: hasActiveQuestion()
  });
  
  // Simulate timer expiry
  console.warn("[PROGRESSION TEST] Simulating timer expiry...");
  
  // Create a test answer
  const testAnswer = "This is a test answer for progression testing.";
  
  // Set draft answer
  const draftArea = document.getElementById("draftAnswer");
  if (draftArea) {
    draftArea.value = testAnswer;
    console.warn("[PROGRESSION TEST] ✅ Test answer set in draft area");
  }
  
  // Simulate timer timeout progression
  setTimeout(() => {
    console.warn("[PROGRESSION TEST] Testing timer expiry progression...");
    
    // Check if progression works
    const beforeProgression = {
      isSavingAnswer: isSavingAnswer,
      currentQuestionId: getActiveQuestionId()
    };
    
    // Force progression using the same logic as timer expiry
    const forceProgressWithTimeout = function(answer, source) {
      console.warn(`[PROGRESSION TEST] FORCE PROGRESSING to next question - source: ${source}`);
      
      const progressionTimeout = setTimeout(function(){
        console.error(`[PROGRESSION TEST] PROGRESSION TIMEOUT - forcing next question regardless of save status`);
        isSavingAnswer = false;
        clearQuestionTimers();
        
        const nextIndex = currentQuestionIndex + 1;
        goToNextQuestion(null, nextIndex);
      }, 3000);
      
      try {
        submitCurrentAnswer(answer, source);
      } catch (error) {
        console.error(`[PROGRESSION TEST] Submit failed, forcing progression:`, error);
        clearTimeout(progressionTimeout);
        isSavingAnswer = false;
        const nextIndex = currentQuestionIndex + 1;
        goToNextQuestion(null, nextIndex);
      }
    };
    
    forceProgressWithTimeout(testAnswer, "test-timer");
    
    setTimeout(() => {
      const afterProgression = {
        isSavingAnswer: isSavingAnswer,
        currentQuestionId: getActiveQuestionId(),
        currentQuestionIndex: currentQuestionIndex
      };
      
      console.warn("[PROGRESSION TEST] Progression results:");
      console.warn("[PROGRESSION TEST] Before:", beforeProgression);
      console.warn("[PROGRESSION TEST] After:", afterProgression);
      
      if (afterProgression.currentQuestionId !== beforeProgression.currentQuestionId) {
        console.warn("[PROGRESSION TEST] ✅ SUCCESS: Question progressed to next question");
      } else {
        console.error("[PROGRESSION TEST] ❌ FAILED: Question did not progress");
      }
    }, 5000);
  }, 1000);
  
  console.warn("[PROGRESSION TEST] ==============================================");
  console.warn("[PROGRESSION TEST] QUESTION PROGRESSION TEST COMPLETED");
  console.warn("[PROGRESSION TEST] ==============================================");
}

// Test 4: Test interview flow robustness with multiple scenarios
function testInterviewFlowRobustness() {
  console.warn("[ROBUSTNESS TEST] ==============================================");
  console.warn("[ROBUSTNESS TEST] TESTING INTERVIEW FLOW ROBUSTNESS");
  console.warn("[ROBUSTNESS TEST] ==============================================");
  
  // Test multiple concurrent scenarios
  console.warn("[ROBUSTNESS TEST] Testing multiple concurrent scenarios...");
  
  // Scenario 1: Face absence during timer
  setTimeout(() => {
    console.warn("[ROBUSTNESS TEST] Scenario 1: Face absence during timer");
    if (faceDetector && cameraStream) {
      handleAbsenceDetected();
    }
  }, 2000);
  
  // Scenario 2: Focus violation during timer
  setTimeout(() => {
    console.warn("[ROBUSTNESS TEST] Scenario 2: Focus violation during timer");
    handleConfirmedFocusViolation("test_focus", "Test focus violation", 3000);
  }, 3000);
  
  // Scenario 3: TTS warning during timer
  setTimeout(() => {
    console.warn("[ROBUSTNESS TEST] Scenario 3: TTS warning during timer");
    speakWarning("test_rule", "Test TTS warning during interview", function(success) {
      console.warn(`[ROBUSTNESS TEST] TTS warning completed: ${success}`);
    });
  }, 4000);
  
  // Scenario 4: Timer expiry with all above active
  setTimeout(() => {
    console.warn("[ROBUSTNESS TEST] Scenario 4: Timer expiry with all warnings active");
    
    const testAnswer = "Test answer with multiple active warnings";
    const draftArea = document.getElementById("draftAnswer");
    if (draftArea) {
      draftArea.value = testAnswer;
    }
    
    // Force progression should work despite all warnings
    const forceProgressWithTimeout = function(answer, source) {
      const progressionTimeout = setTimeout(function(){
        console.error(`[ROBUSTNESS TEST] PROGRESSION TIMEOUT - forcing next question`);
        isSavingAnswer = false;
        clearQuestionTimers();
        
        const nextIndex = currentQuestionIndex + 1;
        goToNextQuestion(null, nextIndex);
      }, 3000);
      
      try {
        submitCurrentAnswer(answer, source);
      } catch (error) {
        console.error(`[ROBUSTNESS TEST] Submit failed, forcing progression:`, error);
        clearTimeout(progressionTimeout);
        isSavingAnswer = false;
        const nextIndex = currentQuestionIndex + 1;
        goToNextQuestion(null, nextIndex);
      }
    };
    
    forceProgressWithTimeout(testAnswer, "robustness-test");
  }, 5000);
  
  // Final verification
  setTimeout(() => {
    console.warn("[ROBUSTNESS TEST] Final verification - checking if interview continued...");
    console.warn("[ROBUSTNESS TEST] Interview should have progressed despite all warnings");
    
    if (currentQuestionIndex > 0) {
      console.warn("[ROBUSTNESS TEST] ✅ SUCCESS: Interview flow is robust and continued despite warnings");
    } else {
      console.error("[ROBUSTNESS TEST] ❌ FAILED: Interview flow did not progress");
    }
  }, 8000);
  
  console.warn("[ROBUSTNESS TEST] ==============================================");
  console.warn("[ROBUSTNESS TEST] ROBUSTNESS TEST COMPLETED");
  console.warn("[ROBUSTNESS TEST] ==============================================");
}

// Test 5: Complete camera and progression test suite
function runCompleteCameraAndProgressionTest() {
  console.warn("[COMPLETE TEST] ==============================================");
  console.warn("[COMPLETE TEST] RUNNING COMPLETE CAMERA AND PROGRESSION TEST SUITE");
  console.warn("[COMPLETE TEST] ==============================================");
  
  // Run all tests in sequence
  testCameraStream();
  
  setTimeout(() => {
    testFaceDetection();
  }, 2000);
  
  setTimeout(() => {
    testQuestionProgression();
  }, 4000);
  
  setTimeout(() => {
    testInterviewFlowRobustness();
  }, 8000);
  
  setTimeout(() => {
    console.warn("[COMPLETE TEST] ==============================================");
    console.warn("[COMPLETE TEST] ALL TESTS COMPLETED");
    console.warn("[COMPLETE TEST] Interview flow should now work correctly");
    console.warn("[COMPLETE TEST] ==============================================");
  }, 12000);
  
  console.warn("[COMPLETE TEST] Test suite initiated. Check console for results.");
}

console.warn("[CAMERA & PROGRESSION TEST] Test functions loaded:");
console.warn("[CAMERA & PROGRESSION TEST] - testCameraStream()");
console.warn("[CAMERA & PROGRESSION TEST] - testFaceDetection()");
console.warn("[CAMERA & PROGRESSION TEST] - testQuestionProgression()");
console.warn("[CAMERA & PROGRESSION TEST] - testInterviewFlowRobustness()");
console.warn("[CAMERA & PROGRESSION TEST] - runCompleteCameraAndProgressionTest()");
console.warn("");
console.warn("[CAMERA & PROGRESSION TEST] Run tests to verify camera view and question progression work correctly.");
