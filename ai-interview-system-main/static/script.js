function speakQuestion() {
        let text = document.getElementById("questionText").innerText;

    const speech = new SpeechSynthesisUtterance();

    speech.text = text;
    speech.lang = "en-US";
    speech.rate = 0.9;
    speech.pitch = 1;

    const voices = speechSynthesis.getVoices();

    if (voices.length > 0) {
        speech.voice = voices[0];
    }

    speechSynthesis.speak(speech);
}

//===========================
// Voice Answer Recognition
// ===========================

function startRecognition() {

    const SpeechRecognition =
        window.SpeechRecognition || window.webkitSpeechRecognition;

    if (!SpeechRecognition) {
        alert("Speech recognition not supported in this browser.");
        return;
    }

    let recognition = new SpeechRecognition();

    recognition.lang = "en-US";
    recognition.continuous = false;
    recognition.interimResults = false;

    recognition.onresult = function(event) {

        let transcript = event.results[0][0].transcript;

        document.getElementById("answer").value = transcript;

    };

    recognition.onerror = function(event) {

        console.log("Voice recognition error:", event.error);

    };

    recognition.start();

}