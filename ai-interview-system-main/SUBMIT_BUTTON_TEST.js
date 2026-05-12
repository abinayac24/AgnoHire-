// Submit Button Test Function
// Use this in browser console to test the submit button

// Test submit button functionality
function testSubmitButton() {
  console.warn("[SUBMIT BUTTON TEST] ==============================================");
  console.warn("[SUBMIT BUTTON TEST] TESTING SUBMIT BUTTON FUNCTIONALITY");
  console.warn("[SUBMIT BUTTON TEST] ==============================================");
  
  // Check if submit button exists
  const submitButton = document.getElementById("submitButton");
  console.warn("[SUBMIT BUTTON TEST] Submit button exists:", !!submitButton);
  
  if (!submitButton) {
    console.error("[SUBMIT BUTTON TEST] ❌ Submit button not found");
    return;
  }
  
  console.warn("[SUBMIT BUTTON TEST] ✅ Submit button found");
  console.warn("[SUBMIT BUTTON TEST] Button text:", submitButton.textContent);
  console.warn("[SUBMIT BUTTON TEST] Button onclick:", !!submitButton.onclick);
  
  // Check if answer box exists
  const answerBox = document.getElementById("answerBox");
  console.warn("[SUBMIT BUTTON TEST] Answer box exists:", !!answerBox);
  
  if (!answerBox) {
    console.error("[SUBMIT BUTTON TEST] ❌ Answer box not found");
    return;
  }
  
  console.warn("[SUBMIT BUTTON TEST] ✅ Answer box found");
  console.warn("[SUBMIT BUTTON TEST] Answer box value:", answerBox.value);
  
  // Test manual submit function exists
  console.warn("[SUBMIT BUTTON TEST] Checking handleManualSubmit function...");
  if (typeof handleManualSubmit === 'function') {
    console.warn("[SUBMIT BUTTON TEST] ✅ handleManualSubmit function exists");
  } else {
    console.error("[SUBMIT BUTTON TEST] ❌ handleManualSubmit function not found");
  }
  
  // Test 1: Submit with empty answer
  console.warn("[SUBMIT BUTTON TEST] Test 1: Submitting empty answer...");
  answerBox.value = "";
  
  try {
    handleManualSubmit();
    console.warn("[SUBMIT BUTTON TEST] ✅ Empty submit test passed");
  } catch (error) {
    console.error("[SUBMIT BUTTON TEST] ❌ Empty submit test failed:", error);
  }
  
  // Test 2: Submit with text answer
  setTimeout(() => {
    console.warn("[SUBMIT BUTTON TEST] Test 2: Submitting text answer...");
    answerBox.value = "This is a test answer for submit button testing.";
    
    try {
      handleManualSubmit();
      console.warn("[SUBMIT BUTTON TEST] ✅ Text submit test passed");
    } catch (error) {
      console.error("[SUBMIT BUTTON TEST] ❌ Text submit test failed:", error);
    }
  }, 2000);
  
  // Test 3: Check button styling and visibility
  setTimeout(() => {
    console.warn("[SUBMIT BUTTON TEST] Test 3: Checking button styling and visibility...");
    
    const buttonStyle = window.getComputedStyle(submitButton);
    console.warn("[SUBMIT BUTTON TEST] Button display:", buttonStyle.display);
    console.warn("[SUBMIT BUTTON TEST] Button visibility:", buttonStyle.visibility);
    console.warn("[SUBMIT BUTTON TEST] Button background:", buttonStyle.backgroundColor);
    console.warn("[SUBMIT BUTTON TEST] Button cursor:", buttonStyle.cursor);
    
    if (buttonStyle.display !== 'none' && buttonStyle.visibility !== 'hidden') {
      console.warn("[SUBMIT BUTTON TEST] ✅ Button is visible and clickable");
    } else {
      console.warn("[SUBMIT BUTTON TEST] ⚠️ Button might be hidden");
    }
  }, 4000);
  
  console.warn("[SUBMIT BUTTON TEST] ==============================================");
  console.warn("[SUBMIT BUTTON TEST] SUBMIT BUTTON TEST COMPLETED");
  console.warn("[SUBMIT BUTTON TEST] ==============================================");
}

// Test submit button integration with answer submission
function testSubmitButtonIntegration() {
  console.warn("[SUBMIT INTEGRATION TEST] ==============================================");
  console.warn("[SUBMIT INTEGRATION TEST] TESTING SUBMIT BUTTON INTEGRATION");
  console.warn("[SUBMIT INTEGRATION TEST] ==============================================");
  
  // Set test answer
  const answerBox = document.getElementById("answerBox");
  if (answerBox) {
    answerBox.value = "Test answer for integration testing.";
    console.warn("[SUBMIT INTEGRATION TEST] Test answer set in box");
  }
  
  // Monitor submitCurrentAnswer calls
  const originalSubmitCurrentAnswer = window.submitCurrentAnswer;
  let submitCallCount = 0;
  
  window.submitCurrentAnswer = function(answer, source) {
    submitCallCount++;
    console.warn(`[SUBMIT INTEGRATION TEST] submitCurrentAnswer called ${submitCallCount} times`);
    console.warn(`[SUBMIT INTEGRATION TEST] Answer: "${answer}"`);
    console.warn(`[SUBMIT INTEGRATION TEST] Source: ${source}`);
    
    // Call original function
    return originalSubmitCurrentAnswer(answer, source);
  };
  
  // Click submit button
  const submitButton = document.getElementById("submitButton");
  if (submitButton) {
    console.warn("[SUBMIT INTEGRATION TEST] Clicking submit button...");
    submitButton.click();
    
    // Check if submission was called
    setTimeout(() => {
      if (submitCallCount > 0) {
        console.warn("[SUBMIT INTEGRATION TEST] ✅ Submit button successfully integrated with answer submission");
      } else {
        console.error("[SUBMIT INTEGRATION TEST] ❌ Submit button integration failed - no submission called");
      }
      
      // Restore original function
      window.submitCurrentAnswer = originalSubmitCurrentAnswer;
    }, 1000);
  }
  
  console.warn("[SUBMIT INTEGRATION TEST] ==============================================");
  console.warn("[SUBMIT INTEGRATION TEST] SUBMIT BUTTON INTEGRATION TEST COMPLETED");
  console.warn("[SUBMIT INTEGRATION TEST] ==============================================");
}

console.warn("[SUBMIT BUTTON TEST] Submit button test functions loaded:");
console.warn("[SUBMIT BUTTON TEST] - testSubmitButton()");
console.warn("[SUBMIT BUTTON TEST] - testSubmitButtonIntegration()");
console.warn("");
console.warn("[SUBMIT BUTTON TEST] Test submit button functionality:");
console.warn("[SUBMIT BUTTON TEST]   testSubmitButton();");
console.warn("[SUBMIT BUTTON TEST]   testSubmitButtonIntegration();");
