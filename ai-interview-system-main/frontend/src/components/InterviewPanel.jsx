import { Button, Card, Group, Text, Textarea } from "@mantine/core";
import { Mic, MicOff, Volume2 } from "lucide-react";

export function InterviewPanel({
  session,
  transcript,
  setTranscript,
  listening,
  onSpeakQuestion,
  submitting
}) {
  return (
    <section className="grid gap-5 lg:grid-cols-[1.4fr_0.9fr] lg:gap-6">
      <Card radius={28} padding="xl" className="glass-panel form-shell text-white">
        <div className="flex items-start justify-between gap-4">
          <div>
            <Text size="xs" fw={600} className="section-label">Live Interview</Text>
            <Text fw={700} size="2rem" mt="md" c="white" className="break-words">{session.candidate_name}</Text>
          </div>
          <div className="neon-chip shrink-0 px-4 py-3 text-sm font-semibold">
            Question {session.current_index + 1} / {session.total_questions}
          </div>
        </div>

        <Card radius={24} padding="xl" mt="xl" className="dark-panel text-white">
          <Text size="xs" fw={700} className="section-label">AI interviewer prompt</Text>
          <Text mt="md" size="1.6rem" fw={500} lh={1.7} c="white">{session.question?.question}</Text>
        </Card>

        <Group mt="xl" className="gap-3">
          <Button
            onClick={onSpeakQuestion}
            radius="xl"
            className="cyan-button font-semibold"
            leftSection={<Volume2 className="h-4 w-4" />}
          >
            Replay AI voice
          </Button>
          <div className="flex items-center gap-2">
            {listening && <span className="flex h-3 w-3 relative"><span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span><span className="relative inline-flex rounded-full h-3 w-3 bg-red-500"></span></span>}
            <span className="text-sm font-semibold">{listening ? "Recording answer..." : (submitting ? "Evaluating..." : "Thinking...")}</span>
          </div>
        </Group>

        <div className="mt-6">
          <Text size="sm" fw={600} mb={8} className="text-slate-300">Captured answer</Text>
          <Textarea
            value={transcript}
            onChange={(event) => setTranscript(event.target.value)}
            minRows={8}
            placeholder={listening ? "Listening to you speak..." : "Waiting for auto-submission..."}
            radius="xl"
            disabled={submitting}
          />
        </div>
      </Card>

      <div className="space-y-5 lg:space-y-6">
        <Card radius={28} padding="lg" className="glass-panel-soft text-white">
          <Text size="xs" fw={700} className="section-label">Interview mode</Text>
          <Text fw={700} size="xl" mt="md" className="capitalize" c="white">{session.mode.replace("-", " ")}</Text>
          {session.candidate_email && (
            <Text mt="sm" size="sm" className="text-slate-400">
              Report delivery: {session.candidate_email}
            </Text>
          )}
          <Text mt="md" size="sm" lh={1.7} className="text-slate-400">
            Only one question is visible at a time. The next question asks automatically. You do NOT have to press anything, just talk after the AI asks you a question.
          </Text>
        </Card>

        <Card radius={28} padding="lg" className="dark-panel text-white">
          <Text size="xs" fw={700} className="section-label">AI greeting</Text>
          <Text mt="md" lh={1.8} className="text-slate-200">{session.greeting}</Text>
        </Card>
      </div>
    </section>
  );
}
