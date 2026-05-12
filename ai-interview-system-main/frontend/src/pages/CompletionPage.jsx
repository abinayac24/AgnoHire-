import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { Shell } from "../components/Shell";
import { getInterviewCompletion } from "../lib/api";

export function CompletionPage() {
  const { sessionId } = useParams();
  const [view, setView] = useState(null);

  useEffect(() => {
    getInterviewCompletion(sessionId).then(setView).catch(() => {
      setView({
        title: "Interview Completed",
        message: "Thank you for attending the interview, Candidate.",
        subtext: "Your results and feedback will be sent to your email within 5 minutes."
      });
    });
  }, [sessionId]);

  return (
    <Shell>
      <div className="glass-panel rounded-[28px] p-10 text-center text-white">
        <p className="section-label text-sm font-semibold uppercase tracking-[0.2em] text-cyan-300">
          Interview Status
        </p>
        <h1 className="mt-4 text-4xl font-semibold">{view?.title || "Interview Completed"}</h1>
        <p className="mt-4 text-lg text-slate-200">{view?.message || ""}</p>
        <p className="mt-2 text-sm text-slate-300">{view?.subtext || ""}</p>
      </div>
    </Shell>
  );
}
