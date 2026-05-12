import { useCallback, useEffect, useState, useRef } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { InterviewPanel } from "../components/InterviewPanel";
import { Shell } from "../components/Shell";
import { ProctoringWarning, ProctoringStatus } from "../components/ProctoringWarning";
import { useSpeechRecognition } from "../hooks/useSpeechRecognition";
import { useSpeechSynthesis } from "../hooks/useSpeechSynthesis";
import { useProctoring } from "../hooks/useProctoring";
import { useVoiceVerification } from "../hooks/useVoiceVerification";
import { getInterviewSession, submitInterviewAnswer } from "../lib/api";

function normalizeVoiceText(text) {
  return (text || "").toLowerCase().replace(/[^\w\s']/g, " ").replace(/\s+/g, " ").trim();
}

function detectVoiceCommand(text) {
  const normalized = normalizeVoiceText(text);
  const words = normalized.split(" ").filter(Boolean);
  if (words.length > 7) return null;

  const phraseGroups = {
    submit: [
      "submit", "submit answer", "submit my answer", "submit it", "final answer",
      "i am done", "i'm done", "im done", "my answer is complete", "that is all", "that's all"
    ],
    repeat: [
      "repeat", "repeat question", "repeat the question", "say again", "ask again",
      "please repeat", "can you repeat", "could you repeat", "pardon"
    ],
    skip: [
      "next", "next question", "next please", "skip", "skip question", "pass",
      "move on", "go to next question", "move to next question"
    ]
  };

  for (const [command, phrases] of Object.entries(phraseGroups)) {
    if (phrases.some((phrase) => normalized === phrase || normalized === `please ${phrase}` || normalized === `${phrase} please`)) {
      return command;
    }
  }

  return null;
}

function getConversationalReply(text, questionText) {
  const normalized = normalizeVoiceText(text);
  const rules = [
    {
      phrases: ["can you hear me", "are you hearing me", "am i audible", "is my voice clear"],
      reply: "Yes, I can hear you clearly. Please continue your answer."
    },
    {
      phrases: ["what was the question", "i did not hear", "i didn't hear", "repeat that"],
      reply: `Sure. ${questionText || ""}`.trim()
    },
    {
      phrases: ["hold on", "one moment", "just a second", "give me a second", "please wait"],
      reply: "Sure. Take a moment. I will keep listening."
    },
    {
      phrases: ["i do not know", "i don't know", "not sure", "i am not sure"],
      reply: "Share what you understand so far. Partial explanations are acceptable."
    },
    {
      phrases: ["clarify the question", "what does that mean", "i don't understand", "i need clarification"],
      reply: "Please answer based on your understanding. I can repeat the question, but I cannot explain the expected answer during the interview."
    },
    {
      phrases: ["did you get my answer", "did you hear that", "was that recorded"],
      reply: "I captured your response. Continue speaking or say submit answer when you are done."
    }
  ];

  const match = rules.find((rule) => rule.phrases.some((phrase) => normalized.includes(phrase)));
  return match?.reply || "";
}

function removeControlPhrases(text) {
  return (text || "")
    .replace(/\b(repeat question|repeat the question|please repeat|can you repeat|could you repeat|say again|ask again|pardon|can you hear me|are you hearing me|am i audible|is my voice clear|submit answer|submit my answer|submit it|final answer|my answer is complete|that is all|that's all|next question|skip question|move on|go to next question|move to next question)\b/gi, "")
    .replace(/\s+/g, " ")
    .trim();
}

export function SessionPage() {
  const { sessionId } = useParams();
  const navigate = useNavigate();

  const [session, setSession] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [latestEvaluation, setLatestEvaluation] = useState(null);
  const [timeLeft, setTimeLeft] = useState(30);
  const [videoElement, setVideoElement] = useState(null);

  const { transcript, setTranscript, listening, startListening, stopListening, supported } = useSpeechRecognition();
  const { speak } = useSpeechSynthesis();

  const [error, setError] = useState(null);

  const hasSpokenGreetingRef = useRef(false);
  const cameraPreviewRef = useRef(null);
  const cameraStreamRef = useRef(null);
  const lastSpokenWarningRef = useRef("");
  const sessionRef = useRef(null);
  const submittingRef = useRef(false);
  const transcriptRef = useRef("");
  const listeningRef = useRef(false);

  // Proctoring integration
  const handleTermination = useCallback((message, rule) => {
    console.error("[Session] Interview terminating due to proctoring violation:", rule, message);
    speak("Interview terminated due to violation: " + message);
    navigate(`/completed/${sessionId}?terminated=true&reason=${encodeURIComponent(rule)}`);
  }, [navigate, sessionId, speak]);

  const { 
    activeWarning, 
    strikeCount, 
    isConnected: proctoringConnected,
    startProctoring, 
    stopProctoring,
    maxWarnings 
  } = useProctoring(sessionId, handleTermination);

  useEffect(() => {
    if (!activeWarning) return;
    if (!["multiple_people", "mobile_phone", "voice_identity", "voice_multi_speaker"].includes(activeWarning.rule)) return;

    const warningKey = `${activeWarning.rule}:${activeWarning.timestamp?.getTime?.() || activeWarning.message}`;
    if (lastSpokenWarningRef.current === warningKey) return;
    lastSpokenWarningRef.current = warningKey;

    const spokenWarnings = {
      multiple_people: activeWarning.count >= maxWarnings
        ? "Final warning. Multiple people are detected in the camera view."
        : "Warning. Multiple people are detected in the camera view. Only the candidate should be visible.",
      mobile_phone: activeWarning.count >= maxWarnings
        ? "Final warning. Mobile phone detected in the camera view."
        : "Warning. Mobile phone detected in the camera view.",
      voice_identity: "Warning. Unauthorized voice detected.",
      voice_multi_speaker: "Warning. Multiple speakers detected.",
    };

    speak(spokenWarnings[activeWarning.rule]);
  }, [activeWarning, maxWarnings, speak]);

  // Voice verification integration
  const handleVoiceMismatch = useCallback((verificationResult) => {
    console.error("[Session] Voice mismatch detected:", verificationResult);
    
    // Create warning for voice mismatch
    const warningData = {
      rule: "voice_identity",
      details: {
        similarity_score: verificationResult.similarity_score,
        warning_level: verificationResult.warning_level,
        is_different_speaker: verificationResult.is_different_speaker,
        timestamp: new Date().toISOString()
      }
    };
    
    // Trigger proctoring warning through WebSocket
    if (window.triggerProctoringWarning) {
      window.triggerProctoringWarning("voice_identity", warningData.details);
    }
    
    // Speak warning
    if (verificationResult.warning_level === "critical") {
      speak("Warning: Different voice detected. Interview will be terminated.");
    } else {
      speak("Warning: Voice verification failed. Please speak clearly.");
    }
  }, [speak]);

  const {
    isEnrolled: voiceEnrolled,
    verificationStatus: voiceStatus,
    similarityScore,
    warningLevel: voiceWarningLevel,
    startVoiceVerification,
    stopVoiceVerification
  } = useVoiceVerification(sessionId, handleVoiceMismatch);

  useEffect(() => {
    sessionRef.current = session;
  }, [sessionId, Boolean(session)]);

  useEffect(() => {
    submittingRef.current = submitting;
  }, [submitting]);

  useEffect(() => {
    transcriptRef.current = transcript;
  }, [transcript]);

  useEffect(() => {
    listeningRef.current = listening;
  }, [listening]);

  useEffect(() => {
    if (!session || cameraStreamRef.current) return undefined;

    let cancelled = false;

    navigator.mediaDevices?.getUserMedia({
      video: { width: 1280, height: 720, facingMode: "user" },
      audio: false,
    }).then((stream) => {
      if (cancelled) {
        stream.getTracks().forEach((track) => track.stop());
        return;
      }

      cameraStreamRef.current = stream;
      const video = cameraPreviewRef.current;
      if (video) {
        video.srcObject = stream;
        video.muted = true;
        video.playsInline = true;
        video.play().catch(() => {});
        setVideoElement(video);
      }
    }).catch((err) => {
      console.error("[Session] Camera access failed:", err);
    });

    return () => {
      cancelled = true;
      cameraStreamRef.current?.getTracks().forEach((track) => track.stop());
      cameraStreamRef.current = null;
      setVideoElement(null);
    };
  }, [session]);

  // Start proctoring when video element is available
  useEffect(() => {
    if (videoElement && sessionId) {
      startProctoring(videoElement);
    }
    return () => {
      stopProctoring();
    };
  }, [videoElement, sessionId, startProctoring, stopProctoring]);

  // Start voice verification when session starts
  useEffect(() => {
    if (session && sessionId) {
      // Start voice verification after a short delay
      const timer = setTimeout(() => {
        console.info("[Session] Starting voice verification");
        startVoiceVerification();
      }, 5000); // Start 5 seconds after session loads
      
      return () => {
        clearTimeout(timer);
        stopVoiceVerification();
      };
    }
  }, [session, sessionId, startVoiceVerification, stopVoiceVerification]);

  const handleFinalPhrase = useCallback((phrase) => {
    const activeSession = sessionRef.current;
    if (submittingRef.current || !activeSession) return;

    const command = detectVoiceCommand(phrase);
    if (command === "submit") {
      handleFinalSubmission();
      return;
    }
    if (command === "skip") {
      submittingRef.current = true;
      setSubmitting(true);
      stopListening({ preferBrowserTranscript: true }).then(() => submitAnswer("NO_ANSWER"));
      return;
    }
    if (command === "repeat") {
      speak(activeSession.question?.question || "");
      return;
    }

    const reply = getConversationalReply(phrase, activeSession.question?.question || "");
    if (reply) {
      speak(reply);
    }
  }, [speak, stopListening]);

  useEffect(() => {
    getInterviewSession(sessionId)
      .then((data) => {
        sessionRef.current = data;
        setSession(data);
        setError(null);
        if (data.greeting && !hasSpokenGreetingRef.current) {
          hasSpokenGreetingRef.current = true;
          speak(`${data.greeting} ${data.question?.question || ""}`, () => {
            startListening(handleSilenceTimeout, handleFinalPhrase);
          });
        }
      })
      .catch((err) => {
        console.error("Failed to load session:", err);
        setError("Session not found or expired. Please start a new interview.");
        // Redirect to home after 3 seconds
        setTimeout(() => navigate("/"), 3000);
      });
  }, [sessionId, speak, startListening, navigate, handleFinalPhrase]);

  // Timer logic
  useEffect(() => {
    if (!session || !listening) return;

    if (timeLeft <= 0) {
      handleFinalSubmission();
      return;
    }

    const timer = setTimeout(() => {
      setTimeLeft((prev) => prev - 1);
    }, 1000);

    return () => clearTimeout(timer);
  }, [timeLeft, session, listening]);

  const handleSilenceTimeout = () => {
    handleFinalSubmission();
  };

  async function handleFinalSubmission() {
    if (submittingRef.current) return;
    submittingRef.current = true;
    setSubmitting(true);
    let finalAnswer = transcriptRef.current;

    if (listeningRef.current) {
      finalAnswer = await stopListening();
    }

    await submitAnswer(finalAnswer);
  }

  async function submitAnswer(textToSubmit) {
    const activeSession = sessionRef.current;
    const cleanedAnswer = removeControlPhrases(textToSubmit);
    if (!cleanedAnswer) {
      speak("I did not hear an answer. Please repeat your answer.", () => {
        setTimeLeft(30);
        startListening(handleSilenceTimeout, handleFinalPhrase);
        submittingRef.current = false;
        setSubmitting(false);
      });
      return;
    }

    try {
      const response = await submitInterviewAnswer(
        sessionId,
        cleanedAnswer,
        activeSession?.question?.id,
        (activeSession?.current_index ?? 0) + 1
      );
      setLatestEvaluation(response.evaluation);
      setTranscript("");
      setTimeLeft(30);

      if (response.completed) {
        navigate(`/completed/${sessionId}`);
        return;
      }

      const nextSession = await getInterviewSession(sessionId);
      sessionRef.current = nextSession;
      setSession(nextSession);

      speak(nextSession.question?.question || "", () => {
        startListening(handleSilenceTimeout, handleFinalPhrase);
        submittingRef.current = false;
        setSubmitting(false);
      });
    } catch (err) {
      console.error("API error", err);
      speak("There was an error saving your answer. Please try again.", () => {
        setTimeLeft(30);
        startListening(handleSilenceTimeout, handleFinalPhrase);
        submittingRef.current = false;
        setSubmitting(false);
      });
    }
  }

  if (error) {
    return (
      <Shell>
        <div className="glass-panel rounded-[28px] p-8 text-white text-center">
          <p className="text-red-400 text-xl mb-4">⚠️ {error}</p>
          <p className="text-slate-400">Redirecting to start page...</p>
        </div>
      </Shell>
    );
  }

  if (!session) {
    return (
      <Shell>
        <div className="glass-panel rounded-[28px] p-8 text-white text-center">
          <p>Loading interview session...</p>
          <p className="text-slate-400 text-sm mt-2">Please wait...</p>
        </div>
      </Shell>
    );
  }

  return (
    <Shell>
      {/* Proctoring Warning Popup */}
      <ProctoringWarning 
        warning={activeWarning} 
        onDismiss={() => {}} 
      />

      {/* Security Status Bar */}
      <div className="mb-4 flex justify-end gap-3">
        <div className="flex items-center gap-3 px-4 py-2 bg-slate-800/80 rounded-full">
          {/* Voice Verification Status */}
          <div className="flex items-center gap-2">
            <div className={`w-2.5 h-2.5 rounded-full ${
              voiceStatus === "active" ? "bg-green-500 animate-pulse" :
              voiceStatus === "verifying" ? "bg-yellow-500 animate-pulse" :
              voiceStatus === "error" ? "bg-red-500" :
              "bg-gray-500"
            }`} />
            <span className="text-xs text-slate-300">
              {voiceStatus === "active" ? "Voice Verified" :
               voiceStatus === "verifying" ? "Verifying..." :
               voiceStatus === "error" ? "Voice Error" :
               "Voice Idle"}
            </span>
          </div>
          
          {/* Proctoring Status */}
          <div className="flex items-center gap-2 pl-3 border-l border-slate-600">
            <div className={`w-2.5 h-2.5 rounded-full ${
              !proctoringConnected ? "bg-gray-500" :
              strikeCount >= maxWarnings - 1 ? "bg-red-500 animate-pulse" :
              strikeCount > 0 ? "bg-yellow-500" :
              "bg-green-500"
            }`} />
            <span className="text-xs text-slate-300">
              {proctoringConnected ? "Proctoring Active" : "Proctoring Offline"}
            </span>
          </div>
          
          {/* Strike Counter */}
          {strikeCount > 0 && (
            <div className="flex items-center gap-1 pl-3 border-l border-slate-600">
              <span className="text-xs text-red-400 font-semibold">
                {strikeCount}/{maxWarnings} Strikes
              </span>
            </div>
          )}
        </div>
      </div>

      {!supported && (
        <div className="mb-6 rounded-3xl border border-amber-400/25 bg-amber-400/10 px-5 py-4 text-sm text-amber-100">
          Browser speech recognition is not available here. You can still type the answer manually and submit it.
        </div>
      )}

      {/* 🔥 SHOW TIMER */}
      {listening && (
        <div className="mb-4 text-white text-lg font-semibold">
          Time Left to Speak: {timeLeft}s
        </div>
      )}

      {latestEvaluation && (
        <div className="glass-panel mb-6 rounded-[28px] p-6 text-white">
          <p className="section-label text-sm font-semibold">Latest evaluation</p>
          <div className="mt-4 grid gap-4 md:grid-cols-3">
            <Metric title="Score" value={`${latestEvaluation.score}%`} />
            <Metric title="Feedback" value={latestEvaluation.feedback} />
            <Metric title="Suggestion" value={latestEvaluation.improvement_suggestion} />
          </div>
        </div>
      )}

      <div className="mb-6 w-full max-w-xs overflow-hidden rounded-3xl border border-cyan-400/20 bg-slate-950/70">
        <video
          ref={cameraPreviewRef}
          autoPlay
          muted
          playsInline
          className="aspect-video w-full bg-black object-cover"
        />
      </div>

      <InterviewPanel
        session={session}
        transcript={transcript}
        setTranscript={setTranscript}
        listening={listening}
        onSpeakQuestion={() => speak(session.question?.question || "")}
        submitting={submitting}
      />
    </Shell>
  );
}

function Metric({ title, value }) {
  return (
    <div className="metric-tile rounded-3xl p-4">
      <p className="text-xs font-semibold uppercase tracking-[0.2em] text-cyan-300">{title}</p>
      <p className="mt-3 text-sm leading-6 text-slate-200">{value}</p>
    </div>
  );
}
