import { useCallback, useEffect, useRef, useState } from "react";
import axios from "axios";

const SILENCE_SUBMIT_MS = 3500;
const WHISPER_TIMEOUT_MS = 6000;

function mergeTranscript(existing, incoming) {
  const left = (existing || "").trim();
  const right = (incoming || "").trim();
  if (!left) return right;
  if (!right) return left;

  const leftWords = left.split(/\s+/);
  const rightWords = right.split(/\s+/);
  const maxOverlap = Math.min(leftWords.length, rightWords.length, 10);

  for (let overlap = maxOverlap; overlap >= 2; overlap -= 1) {
    const leftTail = leftWords.slice(-overlap).join(" ").toLowerCase();
    const rightHead = rightWords.slice(0, overlap).join(" ").toLowerCase();
    if (leftTail === rightHead) {
      return `${leftWords.join(" ")} ${rightWords.slice(overlap).join(" ")}`.replace(/\s+/g, " ").trim();
    }
  }

  if (left.toLowerCase().endsWith(right.toLowerCase())) return left;
  if (right.toLowerCase().startsWith(left.toLowerCase())) return right;
  return `${left} ${right}`.replace(/\s+/g, " ").trim();
}

export function useSpeechRecognition() {
  const recognitionRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const mediaStreamRef = useRef(null);
  const finalTranscriptRef = useRef("");
  const interimTranscriptRef = useRef("");
  const listeningRef = useRef(false);
  const silenceTimerRef = useRef(null);
  const onSilenceRef = useRef(null);
  const onPhraseRef = useRef(null);

  const [transcript, setTranscript] = useState("");
  const [listening, setListening] = useState(false);
  const [supported] = useState(
    Boolean(window.SpeechRecognition || window.webkitSpeechRecognition)
  );

  const renderTranscript = useCallback(() => {
    const draft = mergeTranscript(finalTranscriptRef.current, interimTranscriptRef.current);
    setTranscript(draft);
    return draft;
  }, []);

  const clearSilenceTimer = useCallback(() => {
    if (silenceTimerRef.current) {
      clearTimeout(silenceTimerRef.current);
      silenceTimerRef.current = null;
    }
  }, []);

  const scheduleSilenceSubmit = useCallback(() => {
    clearSilenceTimer();
    silenceTimerRef.current = setTimeout(() => {
      onSilenceRef.current?.();
    }, SILENCE_SUBMIT_MS);
  }, [clearSilenceTimer]);

  useEffect(() => {
    const SpeechRecognition =
      window.SpeechRecognition || window.webkitSpeechRecognition;

    if (!SpeechRecognition) return undefined;

    const recognition = new SpeechRecognition();
    recognition.lang = (navigator.language || "").toLowerCase().startsWith("en-us") ? "en-US" : "en-IN";
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.maxAlternatives = 3;

    recognition.onresult = (event) => {
      let interim = "";

      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const phrase = (event.results[i][0]?.transcript || "").trim();
        if (!phrase) continue;

        if (event.results[i].isFinal) {
          finalTranscriptRef.current = mergeTranscript(finalTranscriptRef.current, phrase);
          onPhraseRef.current?.(phrase);
          scheduleSilenceSubmit();
        } else {
          interim = mergeTranscript(interim, phrase);
        }
      }

      interimTranscriptRef.current = interim;
      renderTranscript();
    };

    recognition.onerror = (event) => {
      if (event.error === "not-allowed") {
        listeningRef.current = false;
        setListening(false);
      }
    };

    recognition.onend = () => {
      if (!listeningRef.current) return;
      setTimeout(() => {
        try {
          recognition.start();
        } catch {
          // Browser recognition can briefly reject restart while it is settling.
        }
      }, 150);
    };

    recognitionRef.current = recognition;

    return () => {
      listeningRef.current = false;
      clearSilenceTimer();
      try {
        recognition.stop();
      } catch {
        // Ignore teardown races.
      }
    };
  }, [clearSilenceTimer, renderTranscript, scheduleSilenceSubmit]);

  const startListening = useCallback(async (onSilenceCallback, onPhraseCallback) => {
    clearSilenceTimer();
    finalTranscriptRef.current = "";
    interimTranscriptRef.current = "";
    audioChunksRef.current = [];
    setTranscript("");
    setListening(true);
    listeningRef.current = true;
    onSilenceRef.current = onSilenceCallback;
    onPhraseRef.current = onPhraseCallback;

    try {
      mediaStreamRef.current = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true
        }
      });

      const mediaRecorder = new MediaRecorder(mediaStreamRef.current);
      mediaRecorderRef.current = mediaRecorder;
      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) audioChunksRef.current.push(event.data);
      };
      mediaRecorder.start();
    } catch (error) {
      console.error("Microphone permission error:", error);
      alert("Please allow microphone access for voice recognition to work.");
    }

    if (recognitionRef.current) {
      try {
        recognitionRef.current.start();
      } catch {
        // Already-started errors are harmless here.
      }
    }
  }, [clearSilenceTimer]);

  const stopListening = useCallback((options = {}) => {
    const preferBrowserTranscript = options.preferBrowserTranscript !== false;

    return new Promise((resolve) => {
      clearSilenceTimer();
      setListening(false);
      listeningRef.current = false;
      onSilenceRef.current = null;
      onPhraseRef.current = null;

      const browserTranscript = renderTranscript();

      try {
        recognitionRef.current?.stop();
      } catch {
        // Ignore stop races.
      }

      const stopTracks = () => {
        mediaStreamRef.current?.getTracks().forEach((track) => track.stop());
        mediaStreamRef.current = null;
      };

      const resolveWith = (value) => {
        stopTracks();
        resolve((value || "").trim());
      };

      if (preferBrowserTranscript && browserTranscript.trim().length >= 3) {
        const recorder = mediaRecorderRef.current;
        if (recorder && recorder.state !== "inactive") {
          recorder.onstop = () => resolveWith(browserTranscript);
          recorder.stop();
        } else {
          resolveWith(browserTranscript);
        }
        return;
      }

      const recorder = mediaRecorderRef.current;
      if (!recorder || recorder.state === "inactive") {
        resolveWith(browserTranscript);
        return;
      }

      recorder.onstop = async () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: "audio/webm" });
        const formData = new FormData();
        formData.append("file", audioBlob, "audio.webm");

        try {
          const response = await axios.post("http://127.0.0.1:9000/transcribe", formData, {
            headers: { "Content-Type": "multipart/form-data" },
            timeout: WHISPER_TIMEOUT_MS
          });
          resolveWith(response.data.text || browserTranscript);
        } catch (error) {
          console.error("Whisper fallback failed:", error.message);
          resolveWith(browserTranscript);
        }
      };

      recorder.stop();
    });
  }, [clearSilenceTimer, renderTranscript]);

  return { transcript, setTranscript, listening, supported, startListening, stopListening };
}
