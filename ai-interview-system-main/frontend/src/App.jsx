import { Navigate, Route, Routes } from "react-router-dom";

import { AdminDashboard } from "./pages/AdminDashboard";
import { CompletionPage } from "./pages/CompletionPage";
import { CompanyStartPage } from "./pages/CompanyStartPage";
import { DomainStartPage } from "./pages/DomainStartPage";
import { EnrollmentPage } from "./pages/EnrollmentPage";
import { HomePage } from "./pages/HomePage";
import { ReportPage } from "./pages/ReportPage";
import { ResumeStartPage } from "./pages/ResumeStartPage";
import { SessionPage } from "./pages/SessionPage";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/start/domain" element={<DomainStartPage />} />
      <Route path="/start/resume" element={<ResumeStartPage />} />
      <Route path="/start/company" element={<CompanyStartPage />} />
      <Route path="/enrollment" element={<EnrollmentPage />} />
      <Route path="/admin" element={<AdminDashboard />} />
      <Route path="/session/:sessionId" element={<SessionPage />} />
      <Route path="/completed/:sessionId" element={<CompletionPage />} />
      <Route path="/report/:sessionId" element={<ReportPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
