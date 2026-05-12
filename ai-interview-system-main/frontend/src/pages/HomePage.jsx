import { Card, List, Text, Title } from "@mantine/core";
import { ArrowRight, Bot, BriefcaseBusiness, FileText, Mic, ShieldCheck } from "lucide-react";
import { motion } from "framer-motion";
import { useNavigate } from "react-router-dom";

import { ModeCard } from "../components/ModeCard";
import { Shell } from "../components/Shell";

export function HomePage() {
  const navigate = useNavigate();
  const heroItems = {
    hidden: { opacity: 0, y: 24 },
    show: {
      opacity: 1,
      y: 0,
      transition: {
        duration: 0.6,
        ease: "easeOut"
      }
    }
  };

  return (
    <Shell>
      <motion.section
        initial="hidden"
        animate="show"
        transition={{ staggerChildren: 0.08 }}
        className="mx-auto max-w-5xl px-2 pt-4 text-center sm:pt-8"
      >
        <motion.div variants={heroItems} className="mx-auto inline-flex items-center rounded-xl border border-red-500/20 bg-red-600 px-4 py-2 text-xs font-bold uppercase tracking-[0.24em] text-white shadow-[0_10px_30px_rgba(216,30,43,0.25)]">
          Admin
        </motion.div>
        <motion.div variants={heroItems} className="mt-14 flex justify-center sm:mt-16">
          <div className="flex h-20 w-20 items-center justify-center rounded-full border border-cyan-400/20 bg-cyan-400/5 shadow-[0_0_0_8px_rgba(31,216,246,0.04),0_0_32px_rgba(31,216,246,0.15)]">
            <Mic className="h-9 w-9 text-cyan-300" />
          </div>
        </motion.div>
        <motion.div variants={heroItems}>
          <Title order={1} className="hero-title mt-8 text-4xl text-white sm:text-6xl md:text-7xl">
          Your interview flow,
          <span className="hero-accent block">reframed with voice-first design</span>
          </Title>
        </motion.div>
        <motion.div variants={heroItems} className="mt-8">
          <span className="neon-chip px-5 py-3 text-xs font-bold uppercase tracking-[0.3em]">
            Voice engine active
          </span>
        </motion.div>
        <motion.div variants={heroItems}>
          <Text className="mx-auto mt-8 max-w-2xl text-base leading-8 text-slate-400 sm:text-lg">
          The workflow stays the same. The interface now feels cleaner, sharper, and more premium across domain, resume, and company-driven interviews.
          </Text>
        </motion.div>

        <motion.div variants={heroItems} className="mt-8 grid gap-3 sm:mt-10 sm:grid-cols-3">
          <StatusTile title="Voice Guided" value="AI-led questions" />
          <StatusTile title="Live Capture" value="Speech or typed answers" />
          <StatusTile title="Instant Report" value="Scored final summary" />
        </motion.div>

        <motion.div variants={heroItems} className="mt-10 flex justify-center">
          <div className="voice-wave" aria-hidden="true">
            {Array.from({ length: 11 }).map((_, index) => (
              <span key={index} style={{ animationDelay: `${index * 120}ms` }} />
            ))}
          </div>
        </motion.div>
      </motion.section>

      <section className="mx-auto mt-10 max-w-2xl sm:mt-12">
        <Card radius={34} padding="xl" className="glass-panel text-center text-white">
          <div className="mx-auto max-w-xl">
            <Text size="xs" fw={700} className="section-label">
              Quick Start
            </Text>
            <Title order={2} className="mt-4 text-3xl text-white sm:text-4xl">
              Launch the same interview system with a more focused visual experience
            </Title>
            <div className="mt-6 flex items-center justify-center gap-3 text-slate-400">
              <ShieldCheck className="h-5 w-5 text-cyan-300" />
              <Text size="sm" className="text-slate-400">
                Structured voice flow, cleaner hierarchy, stronger call-to-action
              </Text>
            </div>
            <div className="mt-8 grid gap-4 sm:grid-cols-2">
              <button
                type="button"
                onClick={() => navigate("/start/domain")}
                className="cyan-button inline-flex items-center justify-center gap-2 rounded-2xl px-6 py-4 text-base font-semibold transition"
              >
                Start with Domain
                <ArrowRight className="h-4 w-4" />
              </button>
              <button
                type="button"
                onClick={() => navigate("/start/resume")}
                className="subtle-button inline-flex items-center justify-center gap-2 rounded-2xl px-6 py-4 text-base font-semibold transition"
              >
                Upload Resume
                <FileText className="h-4 w-4" />
              </button>
            </div>
          </div>
        </Card>
      </section>

      <section className="mx-auto mt-12 max-w-3xl sm:mt-14">
        <Card radius={34} padding="xl" className="glass-panel">
          <Text size="xs" fw={700} className="section-label">
            What you get
          </Text>
          <List spacing="md" mt="lg" size="sm" className="text-slate-300">
            <List.Item>5-question guided interview flow with one question visible at a time.</List.Item>
            <List.Item>Resume parsing, company file extraction, and keyword scoring.</List.Item>
            <List.Item>Final report with strengths, weaknesses, suggestions, and PDF export.</List.Item>
          </List>
        </Card>
      </section>

      <section className="mt-10 grid gap-5 sm:gap-6 lg:grid-cols-3">
        <ModeCard
          title="Domain Based Interview"
          description="Select a technical domain, let the AI greet the candidate, and move through five domain-specific voice questions."
          accentClass="from-cyan-400/5"
          icon={<Bot className="h-7 w-7" />}
          onClick={() => navigate("/start/domain")}
        />
        <ModeCard
          title="Resume Based Interview"
          description="Upload a PDF resume, extract skills and projects, and generate targeted interview questions automatically."
          accentClass="from-cyan-400/5"
          icon={<FileText className="h-7 w-7" />}
          onClick={() => navigate("/start/resume")}
        />
        <ModeCard
          title="Company Based Interview"
          description="Upload PDF, Excel, CSV, or TXT files and run either AI semantic evaluation mode or keyword coverage mode."
          accentClass="from-cyan-400/5"
          icon={<BriefcaseBusiness className="h-7 w-7" />}
          onClick={() => navigate("/start/company")}
        />
      </section>
    </Shell>
  );
}

function StatusTile({ title, value }) {
  return (
    <div className="metric-tile rounded-[24px] px-5 py-4 text-left sm:text-center">
      <p className="text-[11px] font-bold uppercase tracking-[0.28em] text-cyan-300">{title}</p>
      <p className="mt-2 text-sm text-slate-300">{value}</p>
    </div>
  );
}
