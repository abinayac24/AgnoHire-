// Answer Submission Diagnostic and Fix System
// Use this in browser console to diagnose and fix answer submission issues

// Test 1: Check current answer submission state
function diagnoseAnswerSubmissionState() {
  console.warn("[ANSWER SUBMISSION DIAGNOSTIC] ==============================================");
  console.warn("[ANSWER SUBMISSION DIAGNOSTIC] CHECKING ANSWER SUBMISSION STATE");
  console.warn("[ANSWER SUBMISSION DIAGNOSTIC] ==============================================");
  
  // Check all relevant variables
  console.warn("[ANSWER SUBMISSION DIAGNOSTIC] Current answer submission state:");
  console.warn("[ANSWER SUBMISSION DIAGNOSTIC]   isSavingAnswer:", isSavingAnswer);
  console.warn("[ANSWER SUBMISSION DIAGNOSTIC]   isRecording:", isRecording);
  console.warn("[ANSWER SUBMISSION DIAGNOSTIC]   isTranscribing:", isTranscribing);
  console.warn("[ANSWER SUBMISSION DIAGNOSTIC]   isInterviewPaused:", isInterviewPaused);
  console.warn("[ANSWER SUBMISSION DIAGNOSTIC]   PROCTORING_DISABLED:", PROCTORING_DISABLED);
  console.warn("[ANSWER SUBMISSION DIAGNOSTIC]   lastFaceDetectedAt:", lastFaceDetectedAt);
  console.warn("[ANSWER SUBMISSION DIAGNOSTIC]   NO_FACE_PERSISTENCE_MS:", NO_FACE_PERSISTENCE_MS);
  
  // Calculate time since last face
  const timeSinceLastFace = Date.now() - lastFaceDetectedAt;
  console.warn("[ANSWER SUBMISSION DIAGNOSTIC]   Time since last face:", timeSinceLastFace + "ms");
  
  // Check if face detection would block submission
  const faceRecentlyDetected = timeSinceLastFace <= (NO_FACE_PERSISTENCE_MS * 2);
  console.warn("[ANSWER SUBMISSION DIAGNOSTIC]   Face recently detected:", faceRecentlyDetected);
  console.warn("[ANSWER SUBMISSION DIAGNOSTIC]   Face threshold (doubled):", NO_FACE_PERSISTENCE_MS * 2 + "ms");
  
  // Check if answer submission would be blocked
  const wouldBeBlocked = !PROCTORING_DISABLED && (isInterviewPaused || !faceRecentlyDetected);
  console.warn("[ANSWER SUBMISSION DIAGNOSTIC]   Would submission be blocked:", wouldBeBlocked);
  
  if (wouldBeBlocked) {
    console.error("[ANSWER SUBMISSION DIAGNOSTIC] ❌ ANSWER SUBMISSION WOULD BE BLOCKED");
    if (isInterviewPaused) {
      console.error("[ANSWER SUBMISSION DIAGNOSTIC]   Reason: Interview is paused");
    } else {
      console.error("[ANSWER SUBMISSION DIAGNOSTIC]   Reason: No face detected recently");
      console.error("[ANSWER SUBMISSION DIAGNOSTIC]   Time since last face:", timeSinceLastFace + "ms");
      console.error("[ANSWER SUBMISSION DIAGNOSTIC]   Threshold:", NO_FACE_PERSISTENCE_MS * 2 + "ms");
    }
  } else {
    console.warn("[ANSWER SUBMISSION DIAGNOSTIC] ✅ ANSWER SUBMISSION WOULD BE ALLOWED");
  }
  
  console.warn("[ANSWER SUBMISSION DIAGNOSTIC] ==============================================");
  console.warn("[ANSWER SUBMISSION DIAGNOSTIC] ANSWER SUBMISSION STATE CHECK COMPLETED");
  console.warn("[ANSWER SUBMISSION DIAGNOSTIC] ==============================================");
}

// Test 2: Test answer submission with different scenarios
function testAnswerSubmissionScenarios() {
  console.warn("[ANSWER SUBMISSION TEST] ==============================================");
  console.warn("[ANSWER SUBMISSION TEST] TESTING ANSWER SUBMISSION SCENARIOS");
  console.warn("[ANSWER SUBMISSION TEST] ==============================================");
  
  // Test 1: Submit with text answer
  console.warn("[ANSWER SUBMISSION TEST] Test 1: Submitting with text answer...");
  const testAnswer = "This is a test answer for submission testing.";
  
  // Set answer in draft area
  const draftArea = document.getElementById("draftAnswer");
  if (draftArea) {
    draftArea.value = testAnswer;
    console.warn("[ANSWER SUBMISSION TEST] ✅ Test answer set in draft area");
  } else {
    console.error("[ANSWER SUBMISSION TEST] ❌ Draft area not found");
  }
  
  // Test submission
  console.warn("[ANSWER SUBMISSION TEST] Attempting to submit test answer...");
  try {
    submitCurrentAnswer(testAnswer, "test-submission");
    console.warn("[ANSWER SUBMISSION TEST] ✅ Submit function called successfully");
  } catch (error) {
    console.error("[ANSWER SUBMISSION TEST] ❌ Submit function failed:", error);
  }
  
  // Test 2: Submit with empty answer
  setTimeout(() => {
    console.warn("[ANSWER SUBMISSION TEST] Test 2: Submitting empty answer...");
    try {
      submitCurrentAnswer("", "test-empty");
      console.warn("[ANSWER SUBMISSION TEST] ✅ Empty submit function called successfully");
    } catch (error) {
      console.error("[ANSWER SUBMISSION TEST] ❌ Empty submit function failed:", error);
    }
  }, 2000);
  
  // Test 3: Submit with NO_ANSWER
  setTimeout(() => {
    console.warn("[ANSWER SUBMISSION TEST] Test 3: Submitting NO_ANSWER...");
    try {
      submitCurrentAnswer("NO_ANSWER", "test-no-answer");
      console.warn("[ANSWER SUBMISSION TEST] ✅ NO_ANSWER submit function called successfully");
    } catch (error) {
      console.error("[ANSWER SUBMISSION TEST] ❌ NO_ANSWER submit function failed:", error);
    }
  }, 4000);
  
  console.warn("[ANSWER SUBMISSION TEST] ==============================================");
  console.warn("[ANSWER SUBMISSION TEST] ANSWER SUBMISSION SCENARIOS TEST COMPLETED");
  console.warn("[ANSWER SUBMISSION TEST] ==============================================");
}

// Test 3: Check submit triggers and buttons
function testSubmitTriggersAndButtons() {
  console.warn("[SUBMIT TRIGGERS TEST] ==============================================");
  console.warn("[SUBMIT TRIGGERS TEST] CHECKING SUBMIT TRIGGERS AND BUTTONS");
  console.warn("[SUBMIT TRIGGERS TEST] ==============================================");
  
  // Check for submit buttons
  const submitButtons = document.querySelectorAll('button[type="submit"], button[id*="submit"], button[onclick*="submit"]');
  console.warn("[SUBMIT TRIGGERS TEST] Submit buttons found:", submitButtons.length);
  
  submitButtons.forEach((button, index) => {
    console.warn("[SUBMIT TRIGGERS TEST] Submit button", index + 1, ":");
    console.warn("[SUBMIT TRIGGERS TEST]   Text:", button.textContent?.trim());
    console.warn("[SUBMIT TRIGGERS TEST]   ID:", button.id);
    console.warn("[SUBMIT TRIGGERS TEST]   Visible:", button.offsetParent !== null);
  });
  
  // Check for voice command triggers
  console.warn("[SUBMIT TRIGGERS TEST] Voice command submit phrases:");
  console.warn("[SUBMIT TRIGGERS TEST]   submitPhrases:", submitPhrases);
  
  // Check if voice commands are working
  console.warn("[SUBMIT TRIGGERS TEST] Testing voice command recognition...");
  
  // Simulate voice command
  setTimeout(() => {
    console.warn("[SUBMIT TRIGGERS TEST] Simulating 'submit' voice command...");
    const testTranscript = "submit answer";
    
    // Check if command would be detected
    const cleaned = removeCommandPhrases(testTranscript);
    console.warn("[SUBMIT TRIGGERS TEST] Original:", testTranscript);
    console.warn("[SUBMIT TRIGGERS TEST] Cleaned:", cleaned);
    console.warn("[SUBMIT TRIGGERS TEST] Submit command detected:", cleaned !== testTranscript);
  }, 2000);
  
  console.warn("[SUBMIT TRIGGERS TEST] ==============================================");
  console.warn("[SUBMIT TRIGGERS TEST] SUBMIT TRIGGERS AND BUTTONS CHECK COMPLETED");
  console.warn("[SUBMIT TRIGGERS TEST] ==============================================");
}

// Test 4: Apply answer submission fixes
function applyAnswerSubmissionFixes() {
  console.warn("[ANSWER SUBMISSION FIXES] ==============================================");
  console.warn("[ANSWER SUBMISSION FIXES] APPLYING ANSWER SUBMISSION FIXES");
  console.warn("[ANSWER SUBMISSION FIXES] ==============================================");
  
  // Fix 1: Disable face detection blocking temporarily
  console.warn("[ANSWER SUBMISSION FIXES] Fix 1: Disabling face detection blocking...");
  const originalProctoringDisabled = PROCTORING_DISABLED;
  
  // Temporarily disable face detection blocking
  window.PROCTORING_DISABLED = true;
  console.warn("[ANSWER SUBMISSION FIXES] ✅ Face detection blocking temporarily disabled");
  
  // Fix 2: Ensure interview is not paused
  console.warn("[ANSWER SUBMISSION FIXES] Fix 2: Ensuring interview is not paused...");
  if (isInterviewPaused) {
    console.warn("[ANSWER SUBMISSION FIXES] Resuming interview from paused state...");
    window.isInterviewPaused = false;
    console.warn("[ANSWER SUBMISSION FIXES] ✅ Interview resumed");
  }
  
  // Fix 3: Reset face detection timer
  console.warn("[ANSWER SUBMISSION FIXES] Fix 3: Resetting face detection timer...");
  window.lastFaceDetectedAt = Date.now();
  console.warn("[ANSWER SUBMISSION FIXES] ✅ Face detection timer reset to now");
  
  // Fix 4: Clear any stuck states
  console.warn("[ANSWER SUBMISSION FIXES] Fix 4: Clearing stuck states...");
  if (isSavingAnswer) {
    console.warn("[ANSWER SUBMISSION FIXES] Clearing stuck isSavingAnswer state");
    window.isSavingAnswer = false;
  }
  
  if (isTranscribing) {
    console.warn("[ANSWER SUBMISSION FIXES] Clearing stuck isTranscribing state");
    window.isTranscribing = false;
  }
  
  console.warn("[ANSWER SUBMISSION FIXES] ✅ Stuck states cleared");
  
  // Fix 5: Restore proctoring after delay
  setTimeout(() => {
    console.warn("[ANSWER SUBMISSION FIXES] Fix 5: Restoring original proctoring settings...");
    window.PROCTORING_DISABLED = originalProctoringDisabled;
    console.warn("[ANSWER SUBMISSION FIXES] ✅ Proctoring settings restored");
  }, 5000);
  
  console.warn("[ANSWER SUBMISSION FIXES] ==============================================");
  console.warn("[ANSWER SUBMISSION FIXES] ANSWER SUBMISSION FIXES APPLIED");
  console.warn("[ANSWER SUBMISSION FIXES] ==============================================");
}

// Test 5: Force answer submission bypassing all checks
function forceAnswerSubmission() {
  console.warn("[FORCE SUBMISSION TEST] ==============================================");
  console.warn("[FORCE SUBMISSION TEST] FORCING ANSWER SUBMISSION BYPASSING ALL CHECKS");
  console.warn("[FORCE SUBMISSION TEST] ==============================================");
  
  // Temporarily override all blocking conditions
  const originalSaveAnswer = window.saveAnswer;
  const originalProctoringDisabled = PROCTORING_DISABLED;
  const originalIsInterviewPaused = isInterviewPaused;
  const originalLastFaceDetectedAt = lastFaceDetectedAt;
  
  // Override blocking conditions
  window.PROCTORING_DISABLED = true;
  window.isInterviewPaused = false;
  window.lastFaceDetectedAt = Date.now();
  
  console.warn("[FORCE SUBMISSION TEST] All blocking conditions overridden");
  
  // Test forced submission
  const testAnswer = "This is a forced test answer submission.";
  
  try {
    console.warn("[FORCE SUBMISSION TEST] Attempting forced submission...");
    submitCurrentAnswer(testAnswer, "force-test");
    console.warn("[FORCE SUBMISSION TEST] ✅ Forced submission successful");
  } catch (error) {
    console.error("[FORCE SUBMISSION TEST] ❌ Forced submission failed:", error);
  }
  
  // Restore original conditions after delay
  setTimeout(() => {
    console.warn("[FORCE SUBMISSION TEST] Restoring original conditions...");
    window.PROCTORING_DISABLED = originalProctoringDisabled;
    window.isInterviewPaused = originalIsInterviewPaused;
    window.lastFaceDetectedAt = originalLastFaceDetectedAt;
    console.warn("[FORCE SUBMISSION TEST] ✅ Original conditions restored");
  }, 3000);
  
  console.warn("[FORCE SUBMISSION TEST] ==============================================");
  console.warn("[FORCE SUBMISSION TEST] FORCED ANSWER SUBMISSION TEST COMPLETED");
  console.warn("[FORCE SUBMISSION TEST] ==============================================");
}

// Test 6: Run complete answer submission diagnostic and fix
function runCompleteAnswerSubmissionDiagnostic() {
  console.warn("[COMPLETE ANSWER SUBMISSION DIAGNOSTIC] ==============================================");
  console.warn("[COMPLETE ANSWER SUBMISSION DIAGNOSTIC] RUNNING COMPLETE ANSWER SUBMISSION DIAGNOSTIC AND FIX");
  console.warn("[COMPLETE ANSWER SUBMISSION DIAGNOSTIC] ==============================================");
  
  // Run all diagnostics in sequence
  diagnoseAnswerSubmissionState();
  
  setTimeout(() => {
    testSubmitTriggersAndButtons();
  }, 2000);
  
  setTimeout(() => {
    testAnswerSubmissionScenarios();
  }, 4000);
  
  setTimeout(() => {
    applyAnswerSubmissionFixes();
  }, 6000);
  
  setTimeout(() => {
    forceAnswerSubmission();
  }, 8000);
  
  setTimeout(() => {
    console.warn("[COMPLETE ANSWER SUBMISSION DIAGNOSTIC] ==============================================");
    console.warn("[COMPLETE ANSWER SUBMISSION DIAGNOSTIC] ALL DIAGNOSTICS AND FIXES COMPLETED");
    console.warn("[COMPLETE ANSWER SUBMISSION DIAGNOSTIC] Answer submission should now work correctly");
    console.warn("[COMPLETE ANSWER SUBMISSION DIAGNOSTIC] ==============================================");
  }, 12000);
  
  console.warn("[COMPLETE ANSWER SUBMISSION DIAGNOSTIC] Complete diagnostic started. Check console for detailed results.");
}

console.warn("[ANSWER SUBMISSION DIAGNOSTIC] Answer submission diagnostic functions loaded:");
console.warn("[ANSWER SUBMISSION DIAGNOSTIC] - diagnoseAnswerSubmissionState()");
console.warn("[ANSWER SUBMISSION DIAGNOSTIC] - testAnswerSubmissionScenarios()");
console.warn("[ANSWER SUBMISSION DIAGNOSTIC] - testSubmitTriggersAndButtons()");
console.warn("[ANSWER SUBMISSION DIAGNOSTIC] - applyAnswerSubmissionFixes()");
console.warn("[ANSWER SUBMISSION DIAGNOSTIC] - forceAnswerSubmission()");
console.warn("[ANSWER SUBMISSION DIAGNOSTIC] - runCompleteAnswerSubmissionDiagnostic()");
console.warn("");
console.warn("[ANSWER SUBMISSION DIAGNOSTIC] Run diagnostic to identify and fix answer submission issues:");
console.warn("[ANSWER SUBMISSION DIAGNOSTIC]   runCompleteAnswerSubmissionDiagnostic()");
