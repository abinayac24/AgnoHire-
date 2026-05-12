import { useState } from "react";
import { Button, Card, FileInput, SegmentedControl, Text, TextInput, Title } from "@mantine/core";
import { useNavigate } from "react-router-dom";

import { Shell } from "../components/Shell";
import { startCompanyInterview } from "../lib/api";

export function CompanyStartPage() {
  const navigate = useNavigate();
  const [candidateName, setCandidateName] = useState("");
  const [candidateEmail, setCandidateEmail] = useState("");
  const [evaluationMode, setEvaluationMode] = useState("ai");
  const [file, setFile] = useState(null);
  const [isStarting, setIsStarting] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    setIsStarting(true);
    try {
      const formData = new FormData();
      formData.append("candidate_name", candidateName);
      formData.append("candidate_email", candidateEmail);
      formData.append("evaluation_mode", evaluationMode);
      formData.append("question_file", file);
      const session = await startCompanyInterview(formData);
      // Navigate directly to interview - Interview Setup page will handle environment checks
      navigate(`/session/${session.session_id}`);
    } catch (err) {
      console.error("Failed to start interview:", err);
      setIsStarting(false);
    }
  }

  return (
    <Shell>
      <Card radius={32} padding="xl" className="glass-panel form-shell mx-auto max-w-4xl text-white">
        <Text size="xs" fw={700} className="section-label">Company based workflow</Text>
        <Title order={1} className="mt-4 text-4xl text-white">Configure company interview mode</Title>
        <Text className="mt-4 max-w-3xl text-slate-400">
          Upload the company question file and choose how answers should be evaluated. The interview asks only from the uploaded file.
        </Text>

        <SegmentedControl
          mt="xl"
          radius="xl"
          size="md"
          fullWidth
          value={evaluationMode}
          onChange={setEvaluationMode}
          className="segmented-shell rounded-2xl p-1"
          data={[
            { label: "AI Evaluation Mode", value: "ai" },
            { label: "Keyword Based Evaluation", value: "keyword" }
          ]}
        />

        <div className="mt-6 grid gap-4 md:grid-cols-2">
          <ModeInfo
            title="AI Evaluation Mode"
            description="Upload company questions in PDF, Excel, CSV, or TXT. Those exact uploaded questions are asked one by one, and each answer is evaluated by AI."
            active={evaluationMode === "ai"}
          />
          <ModeInfo
            title="Keyword Based Evaluation"
            description="Upload Question + Keywords in PDF, Excel, CSV, or TXT. The system asks those questions and scores answers by keyword coverage."
            active={evaluationMode === "keyword"}
          />
        </div>

        <Card radius={24} padding="lg" mt="xl" className="glass-panel-soft text-white">
          <Text fw={700} c="white">Expected company file behavior</Text>
          <Text mt="sm" size="sm" className="text-slate-300">
            In AI Evaluation Mode, the uploaded file should contain interview questions. In Keyword Based Evaluation, the file should contain each question and its expected keywords.
          </Text>
          <Text mt="sm" size="sm" className="text-slate-400">
            Example: Question: What is REST API? Keywords: HTTP, Stateless, GET, POST, PUT, DELETE, Client Server
          </Text>
        </Card>

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
            <Text size="sm" fw={600} mb={8} className="text-slate-300">Question file</Text>
            <FileInput accept=".pdf,.txt,.csv,.xlsx,.xls" required onChange={setFile} radius="xl" placeholder="Choose question file" />
          </div>

          <Button radius="xl" size="md" className="cyan-button font-semibold" loading={isStarting}>
            {isStarting ? "Starting Interview..." : "Start Interview"}
          </Button>
        </form>
      </Card>
    </Shell>
  );
}

function ModeInfo({ title, description, active }) {
  return (
    <Card
      radius={24}
      padding="lg"
      className={`text-left transition ${active ? "dark-panel text-white" : "glass-panel-soft text-white"}`}
    >
      <Text fw={700} size="lg" c="white">{title}</Text>
      <Text className={`mt-3 text-sm leading-6 ${active ? "text-slate-200" : "text-slate-400"}`}>{description}</Text>
    </Card>
  );
}
