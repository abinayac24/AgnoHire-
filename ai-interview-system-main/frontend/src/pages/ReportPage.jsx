import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { ReportView } from "../components/ReportView";
import { Shell } from "../components/Shell";
import { getInterviewReport, getReportPdfUrl } from "../lib/api";

export function ReportPage() {
  const { sessionId } = useParams();
  const [report, setReport] = useState(null);

  useEffect(() => {
    getInterviewReport(sessionId).then(setReport);
  }, [sessionId]);

  return (
    <Shell>
      {!report ? (
        <div className="glass-panel rounded-[28px] p-8 text-white">Loading final report...</div>
      ) : (
        <ReportView report={report} pdfUrl={getReportPdfUrl(sessionId)} />
      )}
    </Shell>
  );
}
