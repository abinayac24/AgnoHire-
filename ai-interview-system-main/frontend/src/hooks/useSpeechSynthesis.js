import { useCallback, useEffect, useRef } from "react";

export function useSpeechSynthesis() {
  const isSpeakingRef = useRef(false);

  useEffect(() => {
    return () => {
      window.speechSynthesis?.cancel();
    };
  }, []);

  const speak = useCallback((text, onEnd) => {
    if (!("speechSynthesis" in window)) {
      onEnd?.();
      return;
    }

    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = "en-US";
    utterance.rate = 1;
    utterance.pitch = 1;
    isSpeakingRef.current = true;

    utterance.onend = () => {
      isSpeakingRef.current = false;
      onEnd?.();
    };

    utterance.onerror = () => {
      isSpeakingRef.current = false;
      onEnd?.();
    };

    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(utterance);
  }, []);

  return {
    speak,
    isSpeakingRef
  };
}
