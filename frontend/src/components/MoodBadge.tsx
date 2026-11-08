import type { Mood } from "@/lib/types";

export const MOOD_META: Record<Mood, { emoji: string; label: string }> = {
  calm: { emoji: "😌", label: "calm" },
  warm: { emoji: "🙂", label: "warm" },
  happy: { emoji: "😄", label: "happy" },
  concerned: { emoji: "😟", label: "concerned" },
  encouraging: { emoji: "💪", label: "encouraging" },
  serious: { emoji: "😐", label: "serious" },
};

export const MOODS = Object.keys(MOOD_META) as Mood[];

export default function MoodBadge({ mood }: { mood: Mood | null | undefined }) {
  if (!mood) return null;
  const meta = MOOD_META[mood];
  return (
    <span
      title={`Mood: ${meta.label}`}
      className="inline-flex items-center gap-1 rounded-full bg-neutral-100 px-2 py-0.5 text-xs text-neutral-700"
    >
      <span aria-hidden="true">{meta.emoji}</span>
      {meta.label}
    </span>
  );
}
