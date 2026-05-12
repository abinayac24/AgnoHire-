import { useCallback, useEffect, useRef, useState } from "react";

const MAX_WARNINGS = 3;
const WS_RETRY_DELAY = 3000;
const USER_FACING_RULES = new Set([
  "mobile_phone",
  "multiple_people",
  "voice_identity",
  "voice_multi_speaker",
]);

export function useProctoring(sessionId, onTermination) {
  const [warnings, setWarnings] = useState([]);
  const [activeWarning, setActiveWarning] = useState(null);
  const [strikeCount, setStrikeCount] = useState(0);
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const frameIntervalRef = useRef(null);
  const videoRef = useRef(null);

  const connectWebSocket = useCallback(() => {
    if (!sessionId) return;

    const wsUrl = `${import.meta.env.VITE_WS_URL || "ws://localhost:8000"}/api/proctoring/ws`;
    
    try {
      wsRef.current = new WebSocket(wsUrl);

      wsRef.current.onopen = () => {
        console.info("[Proctoring] WebSocket connected");
        setIsConnected(true);
      };

      wsRef.current.onmessage = (event) => {
        const data = JSON.parse(event.data);
        
        if (data.type === "PROCTORING_WARNING") {
          const warning = data.data;
          if (!USER_FACING_RULES.has(warning.rule)) {
            console.info("[Proctoring] Suppressed non-user-facing warning:", warning.rule);
            return;
          }
          const receivedAt = new Date();
          console.warn("[Proctoring] Warning received:", warning);
          
          setActiveWarning({
            rule: warning.rule,
            message: warning.message,
            count: warning.warning_count || 1,
            severity: data.severity,
            timestamp: receivedAt,
          });

          setWarnings((prev) => [...prev, warning]);
          setStrikeCount(warning.total_strikes || 0);

          // Auto-clear warning after 6 seconds
          setTimeout(() => {
            setActiveWarning((current) => 
              current?.timestamp === receivedAt ? null : current
            );
          }, 6000);

          // Check for termination
          if (warning.warning_count >= MAX_WARNINGS) {
            console.error("[Proctoring] Maximum warnings reached - terminating");
            onTermination?.(warning.message, warning.rule);
          }
        }
      };

      wsRef.current.onclose = () => {
        console.info("[Proctoring] WebSocket disconnected");
        setIsConnected(false);
        
        // Auto-reconnect
        reconnectTimeoutRef.current = setTimeout(() => {
          console.info("[Proctoring] Attempting reconnection...");
          connectWebSocket();
        }, WS_RETRY_DELAY);
      };

      wsRef.current.onerror = (error) => {
        console.error("[Proctoring] WebSocket error:", error);
      };

    } catch (err) {
      console.error("[Proctoring] Failed to connect WebSocket:", err);
    }
  }, [sessionId, onTermination]);

  const sendFrame = useCallback((imageBase64) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        session_id: sessionId,
        image_base64: imageBase64,
        include_annotated_image: false,
      }));
    }
  }, [sessionId]);

  const startProctoring = useCallback((videoElement) => {
    if (!videoElement || !sessionId) return;
    
    videoRef.current = videoElement;
    connectWebSocket();

    // Send frames every 2 seconds
    const canvas = document.createElement("canvas");
    const ctx = canvas.getContext("2d");

    frameIntervalRef.current = setInterval(() => {
      if (videoElement.readyState === videoElement.HAVE_ENOUGH_DATA) {
        canvas.width = videoElement.videoWidth;
        canvas.height = videoElement.videoHeight;
        ctx.drawImage(videoElement, 0, 0, canvas.width, canvas.height);
        
        // Compress to reduce payload size
        const imageBase64 = canvas.toDataURL("image/jpeg", 0.7).split(",")[1];
        sendFrame(imageBase64);
      }
    }, 2000);

    console.info("[Proctoring] Started proctoring for session:", sessionId);
  }, [sessionId, connectWebSocket, sendFrame]);

  const stopProctoring = useCallback(() => {
    if (frameIntervalRef.current) {
      clearInterval(frameIntervalRef.current);
      frameIntervalRef.current = null;
    }
    
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    setIsConnected(false);
    console.info("[Proctoring] Stopped proctoring");
  }, []);

  useEffect(() => {
    return () => {
      stopProctoring();
    };
  }, [stopProctoring]);

  return {
    warnings,
    activeWarning,
    strikeCount,
    isConnected,
    startProctoring,
    stopProctoring,
    maxWarnings: MAX_WARNINGS,
  };
}
