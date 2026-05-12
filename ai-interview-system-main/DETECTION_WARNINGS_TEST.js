// Detection Warnings Test Functions
// Use these in browser console to test phone and multi-person detection warnings

// Test 1: Verify phone detection warning message
function testPhoneDetectionWarning() {
  console.warn("[PHONE WARNING TEST] ==============================================");
  console.warn("[PHONE WARNING TEST] TESTING PHONE DETECTION WARNING");
  console.warn("[PHONE WARNING TEST] ==============================================");
  
  // Test phone warning message
  console.warn("[PHONE WARNING TEST] Testing phone warning message...");
  const phoneMessage = PROCTORING_WARNINGS.mobile_phone.message;
  console.warn(`[PHONE WARNING TEST] Expected phone message: "${phoneMessage}"`);
  
  // Test phone warning trigger
  console.warn("[PHONE WARNING TEST] Triggering phone warning...");
  speakWarning("mobile_phone", phoneMessage, function(success) {
    console.warn(`[PHONE WARNING TEST] Phone warning completed: ${success}`);
    console.warn(`[PHONE WARNING TEST] Message displayed: "${phoneMessage}"`);
  });
  
  // Test visual popup
  console.warn("[PHONE WARNING TEST] Testing visual popup...");
  showProctoringPopup(phoneMessage, "mobile_phone");
  
  // Test status updates
  console.warn("[PHONE WARNING TEST] Testing status updates...");
  setTranscriptStatus(phoneMessage);
  setCameraStatus("Camera connected. " + phoneMessage);
  
  console.warn("[PHONE WARNING TEST] ==============================================");
  console.warn("[PHONE WARNING TEST] PHONE DETECTION WARNING TEST COMPLETED");
  console.warn("[PHONE WARNING TEST] ==============================================");
}

// Test 2: Verify multi-person detection warning message
function testMultiPersonDetectionWarning() {
  console.warn("[MULTI-PERSON WARNING TEST] ==============================================");
  console.warn("[MULTI-PERSON WARNING TEST] TESTING MULTI-PERSON DETECTION WARNING");
  console.warn("[MULTI-PERSON WARNING TEST] ==============================================");
  
  // Test multi-person warning message
  console.warn("[MULTI-PERSON WARNING TEST] Testing multi-person warning message...");
  const multiPersonMessage = PROCTORING_WARNINGS.multi_person.message;
  console.warn(`[MULTI-PERSON WARNING TEST] Expected multi-person message: "${multiPersonMessage}"`);
  
  // Test multi-person warning trigger
  console.warn("[MULTI-PERSON WARNING TEST] Triggering multi-person warning...");
  speakWarning("multi_person", multiPersonMessage, function(success) {
    console.warn(`[MULTI-PERSON WARNING TEST] Multi-person warning completed: ${success}`);
    console.warn(`[MULTI-PERSON WARNING TEST] Message displayed: "${multiPersonMessage}"`);
  });
  
  // Test visual popup
  console.warn("[MULTI-PERSON WARNING TEST] Testing visual popup...");
  showProctoringPopup(multiPersonMessage, "multi_person");
  
  // Test status updates
  console.warn("[MULTI-PERSON WARNING TEST] Testing status updates...");
  setTranscriptStatus(multiPersonMessage);
  setCameraStatus("Camera connected. " + multiPersonMessage);
  
  console.warn("[MULTI-PERSON WARNING TEST] ==============================================");
  console.warn("[MULTI-PERSON WARNING TEST] MULTI-PERSON DETECTION WARNING TEST COMPLETED");
  console.warn("[MULTI-PERSON WARNING TEST] ==============================================");
}

// Test 3: Simulate phone detection with vision system
function testPhoneDetectionSimulation() {
  console.warn("[PHONE SIMULATION TEST] ==============================================");
  console.warn("[PHONE SIMULATION TEST] SIMULATING PHONE DETECTION");
  console.warn("[PHONE SIMULATION TEST] ==============================================");
  
  // Create test predictions with phone
  const phonePredictions = [
    { class: "person", score: 0.85, bbox: [100, 100, 200, 400] },
    { class: "cell phone", score: 0.85, bbox: [50, 50, 30, 60] }
  ];
  
  console.warn("[PHONE SIMULATION TEST] Processing phone detection predictions...");
  processVisionDetections(phonePredictions);
  
  setTimeout(() => {
    console.warn("[PHONE SIMULATION TEST] Phone detection simulation completed");
    console.warn("[PHONE SIMULATION TEST] Check for phone warning popup and message");
  }, 2000);
  
  console.warn("[PHONE SIMULATION TEST] ==============================================");
  console.warn("[PHONE SIMULATION TEST] PHONE DETECTION SIMULATION COMPLETED");
  console.warn("[PHONE SIMULATION TEST] ==============================================");
}

// Test 4: Simulate multi-person detection with vision system
function testMultiPersonDetectionSimulation() {
  console.warn("[MULTI-PERSON SIMULATION TEST] ==============================================");
  console.warn("[MULTI-PERSON SIMULATION TEST] SIMULATING MULTI-PERSON DETECTION");
  console.warn("[MULTI-PERSON SIMULATION TEST] ==============================================");
  
  // Create test predictions with multiple people
  const multiPersonPredictions = [
    { class: "person", score: 0.85, bbox: [100, 100, 200, 400] },
    { class: "person", score: 0.72, bbox: [300, 120, 180, 380] }
  ];
  
  console.warn("[MULTI-PERSON SIMULATION TEST] Processing multi-person detection predictions...");
  processVisionDetections(multiPersonPredictions);
  
  setTimeout(() => {
    console.warn("[MULTI-PERSON SIMULATION TEST] Multi-person detection simulation completed");
    console.warn("[MULTI-PERSON SIMULATION TEST] Check for multi-person warning popup and message");
  }, 2000);
  
  console.warn("[MULTI-PERSON SIMULATION TEST] ==============================================");
  console.warn("[MULTI-PERSON SIMULATION TEST] MULTI-PERSON DETECTION SIMULATION COMPLETED");
  console.warn("[MULTI-PERSON SIMULATION TEST] ==============================================");
}

// Test 5: Verify warning states and messages
function testWarningStatesAndMessages() {
  console.warn("[WARNING STATES TEST] ==============================================");
  console.warn("[WARNING STATES TEST] TESTING WARNING STATES AND MESSAGES");
  console.warn("[WARNING STATES TEST] ==============================================");
  
  // Check current warning configuration
  console.warn("[WARNING STATES TEST] Current warning configuration:");
  console.warn("[WARNING STATES TEST] Phone message:", PROCTORING_WARNINGS.mobile_phone.message);
  console.warn("[WARNING STATES TEST] Multi-person message:", PROCTORING_WARNINGS.multi_person.message);
  console.warn("[WARNING STATES TEST] Multiple people message:", PROCTORING_WARNINGS.multiple_people.message);
  
  // Check proctoring disabled state
  console.warn("[WARNING STATES TEST] Proctoring disabled:", PROCTORING_DISABLED);
  console.warn("[WARNING STATES TEST] Face absence detection enabled:", FACE_ABSENCE_DETECTION_ENABLED);
  
  // Test warning state management
  console.warn("[WARNING STATES TEST] Testing warning state management...");
  
  // Reset all warning states
  Object.keys(violationStates).forEach(rule => {
    resetViolationState(rule);
  });
  
  // Test phone warning state
  setViolationState("phone", true);
  console.warn("[WARNING STATES TEST] Phone warning state set:", violationStates.phone);
  
  // Test multi-person warning state
  setViolationState("multi_person", true);
  console.warn("[WARNING STATES TEST] Multi-person warning state set:", violationStates.multi_person);
  
  // Reset states
  setTimeout(() => {
    resetViolationState("phone");
    resetViolationState("multi_person");
    console.warn("[WARNING STATES TEST] Warning states reset");
  }, 3000);
  
  console.warn("[WARNING STATES TEST] ==============================================");
  console.warn("[WARNING STATES TEST] WARNING STATES AND MESSAGES TEST COMPLETED");
  console.warn("[WARNING STATES TEST] ==============================================");
}

// Test 6: Complete detection warnings test suite
function runCompleteDetectionWarningsTest() {
  console.warn("[COMPLETE WARNING TEST] ==============================================");
  console.warn("[COMPLETE WARNING TEST] RUNNING COMPLETE DETECTION WARNINGS TEST SUITE");
  console.warn("[COMPLETE WARNING TEST] ==============================================");
  
  // Run all tests in sequence
  testPhoneDetectionWarning();
  
  setTimeout(() => {
    testMultiPersonDetectionWarning();
  }, 3000);
  
  setTimeout(() => {
    testPhoneDetectionSimulation();
  }, 6000);
  
  setTimeout(() => {
    testMultiPersonDetectionSimulation();
  }, 9000);
  
  setTimeout(() => {
    testWarningStatesAndMessages();
  }, 12000);
  
  setTimeout(() => {
    console.warn("[COMPLETE WARNING TEST] ==============================================");
    console.warn("[COMPLETE WARNING TEST] ALL DETECTION WARNINGS TESTS COMPLETED");
    console.warn("[COMPLETE WARNING TEST] Expected messages:");
    console.warn("[COMPLETE WARNING TEST] - Phone: 'Warning: Mobile phone detected in camera view.'");
    console.warn("[COMPLETE WARNING TEST] - Multi-person: 'Warning: More than 1 person detected in camera view.'");
    console.warn("[COMPLETE WARNING TEST] ==============================================");
  }, 15000);
  
  console.warn("[COMPLETE WARNING TEST] Test suite initiated. Check console for results and UI for warnings.");
}

console.warn("[DETECTION WARNINGS TEST] Test functions loaded:");
console.warn("[DETECTION WARNINGS TEST] - testPhoneDetectionWarning()");
console.warn("[DETECTION WARNINGS TEST] - testMultiPersonDetectionWarning()");
console.warn("[DETECTION WARNINGS TEST] - testPhoneDetectionSimulation()");
console.warn("[DETECTION WARNINGS TEST] - testMultiPersonDetectionSimulation()");
console.warn("[DETECTION WARNINGS TEST] - testWarningStatesAndMessages()");
console.warn("[DETECTION WARNINGS TEST] - runCompleteDetectionWarningsTest()");
console.warn("");
console.warn("[DETECTION WARNINGS TEST] Run tests to verify detection warnings show correct messages:");
console.warn("[DETECTION WARNINGS TEST]   Phone: 'Warning: Mobile phone detected in camera view.'");
console.warn("[DETECTION WARNINGS TEST]   Multi-person: 'Warning: More than 1 person detected in camera view.'");
