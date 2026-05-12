import { useState } from "react";
import { Button, Card, FileInput, Text, TextInput, Title } from "@mantine/core";
import { useNavigate } from "react-router-dom";

import { Shell } from "../components/Shell";
import { startResumeInterview } from "../lib/api";

export function ResumeStartPage() {
  const navigate = useNavigate();
  const [candidateName, setCandidateName] = useState("");
  const [candidateEmail, setCandidateEmail] = useState("");
  const [file, setFile] = useState(null);
  const [isStarting, setIsStarting] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    setIsStarting(true);
    try {
      const formData = new FormData();
      formData.append("candidate_name", candidateName);
      formData.append("candidate_email", candidateEmail);
      formData.append("resume_file", file);
      const session = await startResumeInterview(formData);
      // Navigate directly to interview - Interview Setup page will handle environment checks
      navigate(`/session/${session.session_id}`);
    } catch (err) {
      console.error("Failed to start interview:", err);
      setIsStarting(false);
    }
  }

  return (
    <Shell>
      <Card radius={32} padding="xl" className="glass-panel form-shell mx-auto max-w-3xl text-white">
        <Text size="xs" fw={700} className="section-label">Resume based workflow</Text>
        <Title order={1} className="mt-4 text-4xl text-white">Upload candidate resume</Title>
        <Text className="mt-4 text-slate-400">
          The backend extracts skills, technologies, and projects from PDF content before generating five targeted questions.
        </Text>

        <form onSubmit={handleSubmit} className="mt-8 space-y-5">
          <div>
            <Text size="sm" fw={600} mb={8} className="text-slate-300">Candidate name</Text>
            <TextInput
              value={candidateName}
              onChange={(event) => setCandidateName(event.target.value)}
              required
              placeholder="Enter candidate name"
              radius="xl"
            />
          </div>

          <div>
            <Text size="sm" fw={600} mb={8} className="text-slate-300">Candidate email</Text>
            <TextInput
              type="email"
              value={candidateEmail}
              onChange={(event) => setCandidateEmail(event.target.value)}
              required
              placeholder="Enter candidate email"
              radius="xl"
            />
          </div>

          <div>
            <Text size="sm" fw={600} mb={8} className="text-slate-300">Resume PDF</Text>
            <FileInput accept=".pdf" required onChange={setFile} radius="xl" placeholder="Choose resume PDF" />
          </div>

          <Button radius="xl" size="md" className="cyan-button font-semibold" loading={isStarting}>
            {isStarting ? "Starting Interview..." : "Start Interview"}
          </Button>
        </form>
      </Card>
    </Shell>
  );
}
