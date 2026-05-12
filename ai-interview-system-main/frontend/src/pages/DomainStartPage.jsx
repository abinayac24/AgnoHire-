import { useEffect, useState } from "react";
import { Button, Card, Select, Text, TextInput, Title } from "@mantine/core";
import { useNavigate } from "react-router-dom";

import { Shell } from "../components/Shell";
import { fetchDomains, startDomainInterview } from "../lib/api";

export function DomainStartPage() {
  const navigate = useNavigate();
  const [domains, setDomains] = useState([]);
  const [candidateName, setCandidateName] = useState("");
  const [candidateEmail, setCandidateEmail] = useState("");
  const [domain, setDomain] = useState("");
  const [isStarting, setIsStarting] = useState(false);

  useEffect(() => {
    fetchDomains().then((items) => {
      setDomains(items);
      setDomain(items[0] || "");
    });
  }, []);

  async function handleSubmit(event) {
    event.preventDefault();
    setIsStarting(true);
    try {
      const session = await startDomainInterview({
        candidate_name: candidateName,
        candidate_email: candidateEmail,
        domain
      });
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
        <Text size="xs" fw={700} className="section-label">
          Interview setup
        </Text>
        <Title order={1} className="mt-4 text-4xl text-white">
          Domain Based Interview
        </Title>
        <Text mt="md" className="text-slate-400">
          Choose a domain and begin a five-question AI voice interview.
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
              size="md"
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
              size="md"
            />
          </div>

          <div>
            <Text size="sm" fw={600} mb={8} className="text-slate-300">Domain</Text>
            <Select
              value={domain}
              onChange={(value) => setDomain(value || "")}
              data={domains}
              radius="xl"
              size="md"
            />
          </div>

          <Button radius="xl" size="md" className="cyan-button font-semibold" loading={isStarting}>
            {isStarting ? "Starting Interview..." : "Start Interview"}
          </Button>
        </form>
      </Card>
    </Shell>
  );
}
