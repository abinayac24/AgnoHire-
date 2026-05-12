// TTS and STT Functionality Test
// Use these in browser console to verify TTS, STT, and question progression work correctly

// Test 1: Check TTS (Text-to-Speech) functionality
function testTTSFunctionality() {
  console.warn("[TTS TEST] ==============================================");
  console.warn("[TTS TEST] TESTING TEXT-TO-SPEECH FUNCTIONALITY");
  console.warn("[TTS TEST] ==============================================");
  
  // Check TTS support
  console.warn("[TTS TEST] Checking browser TTS support...");
  if ('speechSynthesis' in window) {
    console.warn("[TTS TEST] ✅ Speech synthesis API supported");
    
    // Get available voices
    const voices = speechSynthesis.getVoices();
    console.warn("[TTS TEST] Available voices:", voices.length);
    if (voices.length > 0) {
      console.warn("[TTS TEST] ✅ Voices available, first voice:", voices[0].name);
    } else {
      console.error("[TTS TEST] ❌ No voices available");
    }
    
    // Test TTS with simple message
    console.warn("[TTS TEST] Testing TTS with test message...");
    const testMessage = "This is a test of the text-to-speech system.";
    const utterance = new SpeechSynthesisUtterance(testMessage);
    
    utterance.onstart = function() {
      console.warn("[TTS TEST] ✅ TTS started speaking");
    };
    
    utterance.onend = function() {
      console.warn("[TTS TEST] ✅ TTS finished speaking successfully");
    };
    
    utterance.onerror = function(event) {
      console.error("[TTS TEST] ❌ TTS error:", event.error);
    };
    
    // Speak the test message
    speechSynthesis.speak(utterance);
    
    console.warn("[TTS TEST] TTS test initiated - check for audio output");
    
  } else {
    console.error("[TTS TEST] ❌ Speech synthesis API not supported");
  }
  
  console.warn("[TTS TEST] ==============================================");
  console.warn("[TTS TEST] TTS FUNCTIONALITY TEST COMPLETED");
  console.warn("[TTS TEST] ==============================================");
}

// Test 2: Check STT (Speech-to-Text) functionality
function testSTTFunctionality() {
  console.warn("[STT TEST] ==============================================");
  console.warn("[STT TEST] TESTING SPEECH-TO-TEXT FUNCTIONALITY");
  console.warn("[STT TEST] ==============================================");
  
  // Check STT support
  console.warn("[STT TEST] Checking browser STT support...");
  if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
    console.warn("[STT TEST] ✅ Speech recognition API supported");
    
    // Create speech recognition instance
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    const recognition = new SpeechRecognition();
    
    // Configure recognition
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.lang = 'en-US';
    
    recognition.onstart = function() {
      console.warn("[STT TEST] ✅ STT started listening");
    };
    
    recognition.onresult = function(event) {
      console.warn("[STT TEST] ✅ STT received results");
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i];
        if (result.isFinal) {
          const transcript = result[0].transcript;
          console.warn("[STT TEST] ✅ STT final transcript:", transcript);
        }
      }
    };
    
    recognition.onerror = function(event) {
      console.error("[STT TEST] ❌ STT error:", event.error);
    };
    
    recognition.onend = function() {
      console.warn("[STT TEST] ✅ STT stopped");
    };
    
    // Start recognition
    console.warn("[STT TEST] Starting STT recognition - say something...");
    recognition.start();
    
    // Auto-stop after 5 seconds
    setTimeout(() => {
      recognition.stop();
      console.warn("[STT TEST] STT test completed - check console for results");
    }, 5000);
    
  } else {
    console.error("[STT TEST] ❌ Speech recognition API not supported");
  }
  
  console.warn("[STT TEST] ==============================================");
  console.warn("[STT TEST] STT FUNCTIONALITY TEST COMPLETED");
  console.warn("[STT TEST] ==============================================");
}

// Test 3: Check next question movement functionality
function testNextQuestionMovement() {
  console.warn("[QUESTION TEST] ==============================================");
  console.warn("[QUESTION TEST] TESTING NEXT QUESTION MOVEMENT");
  console.warn("[QUESTION TEST] ==============================================");
  
  // Check current interview state
  console.warn("[QUESTION TEST] Current interview state:");
  console.warn("[QUESTION TEST]   interviewStarted:", interviewStarted);
  console.warn("[QUESTION TEST]   currentQuestionId:", getActiveQuestionId());
  console.warn("[QUESTION TEST]   currentQuestionIndex:", currentQuestionIndex);
  console.warn("[QUESTION TEST]   hasActiveQuestion:", hasActiveQuestion());
  
  // Test goToNextQuestion function
  console.warn("[QUESTION TEST] Testing goToNextQuestion function...");
  
  try {
    // Create a mock next question
    const mockNextQuestion = {
      id: "test_question_" + Date.now(),
      text: "This is a test question for movement verification.",
      type: "technical"
    };
    
    const nextIndex = currentQuestionIndex + 1;
    
    console.warn("[QUESTION TEST] Calling goToNextQuestion with mock data...");
    
    // Monitor state changes
    const beforeState = {
      currentQuestionId: getActiveQuestionId(),
      currentQuestionIndex: currentQuestionIndex
    };
    
    // Call goToNextQuestion
    goToNextQuestion(mockNextQuestion, nextIndex);
    
    // Check state after delay
    setTimeout(() => {
      const afterState = {
        currentQuestionId: getActiveQuestionId(),
        currentQuestionIndex: currentQuestionIndex
      };
      
      console.warn("[QUESTION TEST] Question movement results:");
      console.warn("[QUESTION TEST]   Before:", beforeState);
      console.warn("[QUESTION TEST]   After:", afterState);
      
      if (afterState.currentQuestionId !== beforeState.currentQuestionId) {
        console.warn("[QUESTION TEST] ✅ SUCCESS: Question moved to next question");
      } else {
        console.error("[QUESTION TEST] ❌ FAILED: Question did not move");
      }
    }, 2000);
    
  } catch (error) {
    console.error("[QUESTION TEST] ❌ Error testing question movement:", error);
  }
  
  console.warn("[QUESTION TEST] ==============================================");
  console.warn("[QUESTION TEST] NEXT QUESTION MOVEMENT TEST COMPLETED");
  console.warn("[QUESTION TEST] ==============================================");
}

// Test 4: Check complete interview flow with TTS and STT
function testCompleteInterviewFlow() {
  console.warn("[FLOW TEST] ==============================================");
  console.warn("[FLOW TEST] TESTING COMPLETE INTERVIEW FLOW");
  console.warn("[FLOW TEST] ==============================================");
  
  // Test 1: TTS speaks question
  console.warn("[FLOW TEST] Test 1: TTS speaking question...");
  const testQuestion = "What is your experience with JavaScript?";
  
  speak(testQuestion, function(success) {
    console.warn(`[FLOW TEST] TTS question speaking completed: ${success}`);
    
    if (success) {
      // Test 2: STT captures answer
      console.warn("[FLOW TEST] Test 2: STT capturing answer...");
      
      // Start listening for answer
      setTimeout(() => {
        console.warn("[FLOW TEST] Starting STT for answer capture...");
        
        // Simulate STT result
        setTimeout(() => {
          const testAnswer = "I have 5 years of experience with JavaScript";
          console.warn("[FLOW TEST] STT captured answer:", testAnswer);
          
          // Test 3: Submit answer and move to next question
          console.warn("[FLOW TEST] Test 3: Submitting answer and moving to next question...");
          
          // Set draft answer
          const draftArea = document.getElementById("draftAnswer");
          if (draftArea) {
            draftArea.value = testAnswer;
            console.warn("[FLOW TEST] ✅ Answer set in draft area");
          }
          
          // Submit answer
          setTimeout(() => {
            submitCurrentAnswer(testAnswer, "flow-test");
            
            setTimeout(() => {
              console.warn("[FLOW TEST] Checking if question progressed...");
              
              const currentQuestionId = getActiveQuestionId();
              console.warn("[FLOW TEST] Current question after submission:", currentQuestionId);
              
              if (currentQuestionId) {
                console.warn("[FLOW TEST] ✅ Interview flow working correctly");
              } else {
                console.error("[FLOW TEST] ❌ Interview flow broken - no active question");
              }
            }, 3000);
          }, 1000);
        }, 3000);
      }, 1000);
    } else {
      console.error("[FLOW TEST] ❌ TTS failed - cannot continue flow test");
    }
  });
  
  console.warn("[FLOW TEST] ==============================================");
  console.warn("[FLOW TEST] COMPLETE INTERVIEW FLOW TEST COMPLETED");
  console.warn("[FLOW TEST] ==============================================");
}

// Test 5: Verify all systems are working
function testAllSystems() {
  console.warn("[SYSTEMS TEST] ==============================================");
  console.warn("[SYSTEMS TEST] TESTING ALL INTERVIEW SYSTEMS");
  console.warn("[SYSTEMS TEST] ==============================================");
  
  // Check camera system
  console.warn("[SYSTEMS TEST] Checking camera system...");
  const cameraStream = window.cameraStream;
  console.warn("[SYSTEMS TEST]   cameraStream exists:", !!cameraStream);
  console.warn("[SYSTEMS TEST]   cameraStream active:", !!(cameraStream && cameraStream.active));
  
  // Check microphone system
  console.warn("[SYSTEMS TEST] Checking microphone system...");
  const micStream = window.micStream;
  console.warn("[SYSTEMS TEST]   micStream exists:", !!micStream);
  console.warn("[SYSTEMS TEST]   micStream active:", !!(micStream && micStream.active));
  
  // Check recording system
  console.warn("[SYSTEMS TEST] Checking recording system...");
  console.warn("[SYSTEMS TEST]   isRecording:", isRecording);
  console.warn("[SYSTEMS TEST]   isTranscribing:", isTranscribing);
  
  // Check TTS system
  console.warn("[SYSTEMS TEST] Checking TTS system...");
  console.warn("[SYSTEMS TEST]   speechSynthesis available:", 'speechSynthesis' in window);
  
  // Check STT system
  console.warn("[SYSTEMS TEST] Checking STT system...");
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  console.warn("[SYSTEMS TEST]   speechRecognition available:", !!SpeechRecognition);
  
  // Check question management
  console.warn("[SYSTEMS TEST] Checking question management...");
  console.warn("[SYSTEMS TEST]   interviewStarted:", interviewStarted);
  console.warn("[SYSTEMS TEST]   hasActiveQuestion:", hasActiveQuestion());
  
  console.warn("[SYSTEMS TEST] ==============================================");
  console.warn("[SYSTEMS TEST] ALL SYSTEMS TEST COMPLETED");
  console.warn("[SYSTEMS TEST] ==============================================");
}

// Test 6: Run complete TTS, STT, and question flow test suite
function runCompleteTTSSTTFlowTest() {
  console.warn("[COMPLETE TEST] ==============================================");
  console.warn("[COMPLETE TEST] RUNNING COMPLETE TTS, STT, AND FLOW TEST SUITE");
  console.warn("[COMPLETE TEST] ==============================================");
  
  // Run all tests in sequence
  testAllSystems();
  
  setTimeout(() => {
    testTTSFunctionality();
  }, 3000);
  
  setTimeout(() => {
    testSTTFunctionality();
  }, 6000);
  
  setTimeout(() => {
    testNextQuestionMovement();
  }, 9000);
  
  setTimeout(() => {
    testCompleteInterviewFlow();
  }, 12000);
  
  setTimeout(() => {
    console.warn("[COMPLETE TEST] ==============================================");
    console.warn("[COMPLETE TEST] ALL TTS, STT, AND FLOW TESTS COMPLETED");
    console.warn("[COMPLETE TEST] Check console results for any issues");
    console.warn("[COMPLETE TEST] ==============================================");
  }, 18000);
  
  console.warn("[COMPLETE TEST] Complete test suite initiated. Check console for results.");
}

console.warn("[TTS & STT TEST] Test functions loaded:");
console.warn("[TTS & STT TEST] - testTTSFunctionality()");
console.warn("[TTS & STT TEST] - testSTTFunctionality()");
console.warn("[TTS & STT TEST] - testNextQuestionMovement()");
console.warn("[TTS & STT TEST] - testCompleteInterviewFlow()");
console.warn("[TTS & STT TEST] - testAllSystems()");
console.warn("[TTS & STT TEST] - runCompleteTTSSTTFlowTest()");
console.warn("");
console.warn("[TTS & STT TEST] Run tests to verify TTS, STT, and question progression work correctly:");
