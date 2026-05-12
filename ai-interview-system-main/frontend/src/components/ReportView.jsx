import { Anchor, Card, SimpleGrid, Text, Title } from "@mantine/core";
import { Download } from "lucide-react";

export function ReportView({ report, pdfUrl }) {
  return (
    <section className="space-y-6">
      <Card radius={30} padding="xl" className="glass-panel text-white">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <Text size="xs" fw={700} className="section-label">Final Report</Text>
            <Title order={1} className="mt-3 text-4xl text-white">{report.candidate_name}</Title>
            <Text mt="md" className="capitalize text-slate-400">{report.mode.replace("-", " ")} interview</Text>
            {report.candidate_email && (
              <Text mt="sm" className="text-slate-400">{report.candidate_email}</Text>
            )}
          </div>
          <Card radius={28} padding="lg" className="dark-panel text-white">
            <Text size="xs" fw={700} className="section-label">Overall score</Text>
            <Text mt="sm" fw={700} size="3rem" c="white">{report.overall_score}%</Text>
          </Card>
        </div>

        <Anchor
          href={pdfUrl}
          target="_blank"
          rel="noreferrer"
          className="cyan-button mt-8 inline-flex items-center gap-2 rounded-2xl px-5 py-3 font-semibold no-underline"
        >
          <Download className="h-4 w-4" />
          Export PDF report
        </Anchor>
      </Card>

      <SimpleGrid cols={{ base: 1, lg: 3 }} spacing="lg">
        <InsightCard title="Strengths" items={report.strengths} />
        <InsightCard title="Weaknesses" items={report.weaknesses} />
        <InsightCard title="Improvements" items={report.improvement_suggestions} />
      </SimpleGrid>

      <div className="space-y-4">
        {report.items.map((item, index) => (
          <Card key={item.question} radius={28} padding="lg" className="glass-panel-soft text-white">
            <div className="flex items-start justify-between gap-5">
              <div>
                <Text size="xs" fw={700} className="section-label">Question {index + 1}</Text>
                <Title order={3} className="mt-3 text-xl text-white">{item.question}</Title>
              </div>
              <div className="neon-chip px-4 py-3 text-lg font-bold">{item.score}%</div>
            </div>
            <Text mt="lg" size="sm" lh={1.8} className="text-slate-300"><strong className="text-white">Answer:</strong> {item.answer}</Text>
            <Text mt="md" size="sm" lh={1.8} className="text-slate-300"><strong className="text-white">Feedback:</strong> {item.feedback}</Text>
            <Text mt="md" size="sm" lh={1.8} className="text-slate-300"><strong className="text-white">Suggestion:</strong> {item.improvement_suggestion}</Text>
          </Card>
        ))}
      </div>
    </section>
  );
}

function InsightCard({ title, items }) {
  return (
    <Card radius={28} padding="lg" className="glass-panel-soft text-white">
      <Text size="xs" fw={700} className="section-label">{title}</Text>
      <div className="mt-4 space-y-3">
        {items.map((item) => (
          <Text key={item} className="metric-tile rounded-2xl px-4 py-3 text-sm leading-6 text-slate-300">
            {item}
          </Text>
        ))}
      </div>
    </Card>
  );
}
