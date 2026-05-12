import { useEffect, useState } from "react";

const WARNING_MESSAGES = {
  mobile_phone: {
    icon: "📱",
    title: "MOBILE PHONE DETECTED",
    color: "from-red-600 to-red-800",
    borderColor: "border-red-400",
  },
  multi_person: {
    icon: "👥",
    title: "MULTIPLE PEOPLE DETECTED",
    color: "from-orange-600 to-red-700",
    borderColor: "border-orange-400",
  },
  multiple_people: {
    icon: "!",
    title: "MULTIPLE PEOPLE DETECTED",
    color: "from-orange-600 to-red-700",
    borderColor: "border-orange-400",
  },
  identity_mismatch: {
    icon: "🚫",
    title: "UNAUTHORIZED PERSON",
    color: "from-red-700 to-red-900",
    borderColor: "border-red-500",
  },
  eye_gaze: {
    icon: "👀",
    title: "LOOKING AWAY",
    color: "from-yellow-600 to-orange-700",
    borderColor: "border-yellow-400",
  },
  head_pose: {
    icon: "🔄",
    title: "SUSPICIOUS HEAD MOVEMENT",
    color: "from-yellow-600 to-orange-700",
    borderColor: "border-yellow-400",
  },
  partial_human: {
    icon: "👤",
    title: "SECONDARY PERSON DETECTED",
    color: "from-orange-600 to-red-700",
    borderColor: "border-orange-400",
  },
  unauthorized_device: {
    icon: "💻",
    title: "UNAUTHORIZED DEVICE",
    color: "from-red-600 to-red-800",
    borderColor: "border-red-400",
  },
  assistance_suspected: {
    icon: "🆘",
    title: "ASSISTANCE SUSPECTED",
    color: "from-red-700 to-red-900",
    borderColor: "border-red-500",
  },
  reading_pattern: {
    icon: "📖",
    title: "SUSPICIOUS READING",
    color: "from-yellow-600 to-orange-700",
    borderColor: "border-yellow-400",
  },
  default: {
    icon: "⚠️",
    title: "PROCTORING WARNING",
    color: "from-red-600 to-red-800",
    borderColor: "border-red-400",
  },
};

export function ProctoringWarning({ warning, onDismiss }) {
  const [isVisible, setIsVisible] = useState(false);
  const [progress, setProgress] = useState(100);

  useEffect(() => {
    if (warning) {
      setIsVisible(true);
      setProgress(100);
      
      const duration = 6000; // 6 seconds
      const interval = 50; // Update every 50ms
      const step = 100 / (duration / interval);
      
      const progressInterval = setInterval(() => {
        setProgress((prev) => {
          const next = prev - step;
          if (next <= 0) {
            clearInterval(progressInterval);
            return 0;
          }
          return next;
        });
      }, interval);

      const hideTimeout = setTimeout(() => {
        setIsVisible(false);
        onDismiss?.();
      }, duration);

      return () => {
        clearInterval(progressInterval);
        clearTimeout(hideTimeout);
      };
    }
  }, [warning, onDismiss]);

  if (!warning || !isVisible) return null;

  const config = WARNING_MESSAGES[warning.rule] || WARNING_MESSAGES.default;
  const isFinalWarning = warning.count >= 3;
  const isCritical = isFinalWarning || warning.severity === "critical";

  return (
    <div className="fixed inset-0 z-[999999] flex items-center justify-center">
      {/* Backdrop */}
      <div 
        className="absolute inset-0 bg-black/70 backdrop-blur-sm"
        onClick={() => setIsVisible(false)}
      />
      
      {/* Warning Card */}
      <div 
        className={`
          relative w-full max-w-md mx-4 
          bg-gradient-to-br ${config.color}
          ${config.borderColor} border-4
          rounded-2xl p-6 shadow-2xl
          transform transition-all duration-300
          ${isVisible ? "scale-100 opacity-100" : "scale-90 opacity-0"}
          ${isCritical ? "animate-pulse" : ""}
        `}
      >
        {/* Progress Bar */}
        <div className="absolute top-0 left-0 right-0 h-1 bg-white/20 rounded-t-2xl overflow-hidden">
          <div 
            className="h-full bg-white transition-all duration-100 ease-linear"
            style={{ width: `${progress}%` }}
          />
        </div>

        {/* Icon */}
        <div className="text-center mb-4">
          <span className="text-6xl">{config.icon}</span>
        </div>

        {/* Title */}
        <h2 className={`
          text-center text-xl font-bold text-white mb-2
          ${isFinalWarning ? "text-red-200" : ""}
        `}>
          {isFinalWarning ? "🚨 FINAL WARNING 🚨" : config.title}
        </h2>

        {/* Message */}
        <p className="text-center text-white/90 text-lg mb-4 leading-relaxed">
          {warning.message}
        </p>

        {/* Strike Counter */}
        <div className="flex justify-center items-center gap-2 mb-4">
          {[1, 2, 3].map((strike) => (
            <div
              key={strike}
              className={`
                w-10 h-10 rounded-full flex items-center justify-center
                font-bold text-lg transition-all duration-300
                ${strike <= warning.count 
                  ? "bg-red-500 text-white shadow-lg shadow-red-500/50" 
                  : "bg-white/20 text-white/50"}
                ${strike === warning.count && isCritical ? "animate-bounce" : ""}
              `}
            >
              {strike}
            </div>
          ))}
        </div>

        {/* Warning Text */}
        <p className="text-center text-white/70 text-sm">
          {isFinalWarning 
            ? "⚠️ Interview will be terminated on next violation"
            : `${warning.count} of ${3} warnings before termination`
          }
        </p>

        {/* Dismiss Button */}
        <button
          onClick={() => setIsVisible(false)}
          className="
            mt-4 w-full py-3 px-4
            bg-white/20 hover:bg-white/30
            text-white font-semibold rounded-xl
            transition-colors duration-200
            backdrop-blur-sm
          "
        >
          I Understand
        </button>
      </div>
    </div>
  );
}

export function ProctoringStatus({ isConnected, strikeCount, maxWarnings }) {
  const getStatusColor = () => {
    if (!isConnected) return "bg-gray-500";
    if (strikeCount >= maxWarnings - 1) return "bg-red-500 animate-pulse";
    if (strikeCount > 0) return "bg-yellow-500";
    return "bg-green-500";
  };

  return (
    <div className="flex items-center gap-3 px-4 py-2 bg-slate-800/80 rounded-full">
      {/* Connection Status */}
      <div className="flex items-center gap-2">
        <div className={`w-2.5 h-2.5 rounded-full ${getStatusColor()}`} />
        <span className="text-xs text-slate-300">
          {isConnected ? "Proctoring Active" : "Proctoring Offline"}
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
  );
}
