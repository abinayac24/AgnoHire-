import { Card, Group, Text, ThemeIcon } from "@mantine/core";
import { motion } from "framer-motion";
import { ArrowRight } from "lucide-react";

export function ModeCard({ title, description, accentClass, icon, onClick }) {
  return (
    <motion.button
      initial={{ opacity: 0, y: 18 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.25 }}
      transition={{ duration: 0.45, ease: "easeOut" }}
      whileHover={{ y: -8, scale: 1.01 }}
      whileTap={{ scale: 0.99 }}
      onClick={onClick}
      className="group h-full text-left"
    >
      <Card
        radius={28}
        padding="xl"
        className={`glass-panel-soft relative h-full overflow-hidden text-white ${accentClass}`}
      >
        <div className="absolute inset-0 bg-gradient-to-br from-cyan-400/10 via-transparent to-blue-500/10 opacity-0 transition duration-300 group-hover:opacity-100" />
        <div className="absolute -right-12 -top-12 h-28 w-28 rounded-full bg-cyan-400/10 blur-2xl transition duration-300 group-hover:bg-cyan-400/15" />
        <div className="relative flex h-full flex-col">
          <ThemeIcon
            size={56}
            radius={18}
            variant="light"
            className="border border-cyan-400/25 bg-cyan-400/10 text-cyan-300 shadow-[0_0_20px_rgba(31,216,246,0.08)]"
          >
            {icon}
          </ThemeIcon>
          <Text fw={700} size="xl" mt="xl" c="white">
            {title}
          </Text>
          <Text size="sm" lh={1.8} mt="sm" className="text-slate-300">
            {description}
          </Text>
          <Group gap={8} mt={32} className="text-sm font-semibold text-cyan-300">
            <span>Start workflow</span>
            <ArrowRight className="h-4 w-4 transition group-hover:translate-x-1" />
          </Group>
        </div>
      </Card>
    </motion.button>
  );
}
