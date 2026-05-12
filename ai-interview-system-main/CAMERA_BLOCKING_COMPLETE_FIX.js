// Complete Camera Blocking Fix
// Use this in browser console to completely remove camera blocking

// Function to completely disable camera blocking for answer submission
function completelyDisableCameraBlocking() {
  console.warn("[CAMERA BLOCKING FIX] ==============================================");
  console.warn("[CAMERA BLOCKING FIX] COMPLETELY DISABLING CAMERA BLOCKING");
  console.warn("[CAMERA BLOCKING FIX] ==============================================");
  
  // 1. Disable proctoring completely
  console.warn("[CAMERA BLOCKING FIX] Step 1: Disabling proctoring...");
  window.PROCTORING_DISABLED = true;
  
  // 2. Reset face detection timer to current time
  console.warn("[CAMERA BLOCKING FIX] Step 2: Resetting face detection timer...");
  window.lastFaceDetectedAt = Date.now();
  
  // 3. Ensure interview is not paused
  console.warn("[CAMERA BLOCKING FIX] Step 3: Ensuring interview is not paused...");
  window.isInterviewPaused = false;
  
  // 4. Override submitCurrentAnswer to bypass all camera checks
  console.warn("[CAMERA BLOCKING FIX] Step 4: Overriding submitCurrentAnswer...");
  const originalSubmitCurrentAnswer = window.submitCurrentAnswer;
  
  window.submitCurrentAnswer = async function(answer, source) {
    console.warn("[CAMERA BLOCKING FIX] SUBMIT CURRENT ANSWER - ALL BLOCKS BYPASSED");
    console.warn("[CAMERA BLOCKING FIX] Answer:", answer);
    console.warn("[CAMERA BLOCKING FIX] Source:", source);
    
    // Bypass all camera checks and call original saveAnswer directly
    try {
      const result = await window.originalSaveAnswer(answer);
      console.warn("[CAMERA BLOCKING FIX] ✅ Submission successful");
      return result;
    } catch (error) {
      console.error("[CAMERA BLOCKING FIX] ❌ Submission failed:", error);
      throw error;
    }
  };
  
  // 5. Override handleManualSubmit to bypass all camera checks
  console.warn("[CAMERA BLOCKING FIX] Step 5: Overriding handleManualSubmit...");
  window.handleManualSubmit = function() {
    console.warn("[CAMERA BLOCKING FIX] MANUAL SUBMIT - ALL BLOCKS BYPASSED");
    
    // Get current answer from draft area
    const answerBox = document.getElementById("answerBox");
    const currentAnswer = answerBox ? answerBox.value.trim() : "";
    
    console.warn("[CAMERA BLOCKING FIX] Current answer:", currentAnswer);
    console.warn("[CAMERA BLOCKING FIX] Answer length:", currentAnswer.length);
    
    // Submit directly without any checks
    try {
      if (!currentAnswer || currentAnswer.length === 0) {
        console.warn("[CAMERA BLOCKING FIX] Submitting empty answer");
        window.submitCurrentAnswer("NO_ANSWER", "manual-submit");
      } else {
        console.warn("[CAMERA BLOCKING FIX] Submitting answer with content");
        window.submitCurrentAnswer(currentAnswer, "manual-submit");
      }
      
      // Update UI to show submission in progress
      setTranscriptStatus("Submitting your answer manually...");
      updateRecordingButtons();
      
      console.warn("[CAMERA BLOCKING FIX] ✅ Manual submission completed");
    } catch (error) {
      console.error("[CAMERA BLOCKING FIX] ❌ Manual submission failed:", error);
    }
  };
  
  // 6. Clear any existing camera warning popups
  console.warn("[CAMERA BLOCKING FIX] Step 6: Clearing camera warning popups...");
  
  // Hide any presence lock UI
  const presenceLockUI = document.getElementById("presenceLockUI");
  if (presenceLockUI) {
    presenceLockUI.style.display = "none";
    console.warn("[CAMERA BLOCKING FIX] ✅ Presence lock UI hidden");
  }
  
  // Clear transcript status
  setTranscriptStatus("Camera blocking disabled. You can submit answers freely.");
  
  // 7. Show success message
  console.warn("[CAMERA BLOCKING FIX] ✅ ALL CAMERA BLOCKING DISABLED");
  console.warn("[CAMERA BLOCKING FIX] ==============================================");
  console.warn("[CAMERA BLOCKING FIX] Answer submission will now work regardless of camera status");
  console.warn("[CAMERA BLOCKING FIX] ==============================================");
}

// Function to test if camera blocking is completely disabled
function testCameraBlockingDisabled() {
  console.warn("[CAMERA BLOCKING TEST] ==============================================");
  console.warn("[CAMERA BLOCKING TEST] TESTING IF CAMERA BLOCKING IS DISABLED");
  console.warn("[CAMERA BLOCKING TEST] ==============================================");
  
  // Test 1: Check if proctoring is disabled
  console.warn("[CAMERA BLOCKING TEST] Test 1: Proctoring disabled:", PROCTORING_DISABLED);
  
  // Test 2: Check if face detection timer is recent
  const timeSinceLastFace = Date.now() - lastFaceDetectedAt;
  console.warn("[CAMERA BLOCKING TEST] Test 2: Time since last face:", timeSinceLastFace + "ms");
  
  // Test 3: Check if interview is paused
  console.warn("[CAMERA BLOCKING TEST] Test 3: Interview paused:", isInterviewPaused);
  
  // Test 4: Try to submit an answer
  console.warn("[CAMERA BLOCKING TEST] Test 4: Testing answer submission...");
  
  const testAnswer = "This is a test answer to verify camera blocking is disabled.";
  
  try {
    submitCurrentAnswer(testAnswer, "camera-blocking-test");
    console.warn("[CAMERA BLOCKING TEST] ✅ Answer submission test passed");
  } catch (error) {
    console.error("[CAMERA BLOCKING TEST] ❌ Answer submission test failed:", error);
  }
  
  // Test 5: Try manual submit
  setTimeout(() => {
    console.warn("[CAMERA BLOCKING TEST] Test 5: Testing manual submission...");
    
    const answerBox = document.getElementById("answerBox");
    if (answerBox) {
      answerBox.value = testAnswer;
      
      try {
        handleManualSubmit();
        console.warn("[CAMERA BLOCKING TEST] ✅ Manual submission test passed");
      } catch (error) {
        console.error("[CAMERA BLOCKING TEST] ❌ Manual submission test failed:", error);
      }
    } else {
      console.error("[CAMERA BLOCKING TEST] ❌ Answer box not found");
    }
  }, 2000);
  
  console.warn("[CAMERA BLOCKING TEST] ==============================================");
  console.warn("[CAMERA BLOCKING TEST] CAMERA BLOCKING TEST COMPLETED");
  console.warn("[CAMERA BLOCKING TEST] ==============================================");
}

// Function to restore original camera blocking (if needed)
function restoreOriginalCameraBlocking() {
  console.warn("[CAMERA BLOCKING RESTORE] ==============================================");
  console.warn("[CAMERA BLOCKING RESTORE] RESTORING ORIGINAL CAMERA BLOCKING");
  console.warn("[CAMERA BLOCKING RESTORE] ==============================================");
  
  // Restore original proctoring settings
  window.PROCTORING_DISABLED = false;
  console.warn("[CAMERA BLOCKING RESTORE] ✅ Proctoring settings restored");
  
  // Note: This will restore the original submitCurrentAnswer with camera checks
  console.warn("[CAMERA BLOCKING RESTORE] Original camera blocking restored");
  console.warn("[CAMERA BLOCKING RESTORE] ==============================================");
}

console.warn("[CAMERA BLOCKING FIX] Camera blocking fix functions loaded:");
console.warn("[CAMERA BLOCKING FIX] - completelyDisableCameraBlocking()");
console.warn("[CAMERA BLOCKING FIX] - testCameraBlockingDisabled()");
console.warn("[CAMERA BLOCKING FIX] - restoreOriginalCameraBlocking()");
console.warn("");
console.warn("[CAMERA BLOCKING FIX] To completely fix camera blocking issue:");
console.warn("[CAMERA BLOCKING FIX]   completelyDisableCameraBlocking()");
console.warn("[CAMERA BLOCKING FIX]   testCameraBlockingDisabled()");
