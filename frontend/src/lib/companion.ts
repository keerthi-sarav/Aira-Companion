import type { CompanionFormValues, Industry } from "./types";

/** Client-side limits. These mirror the backend field limits in docs/ARCHITECTURE.md section 5. */
export const LIMITS = {
  name: 80,
  role: 200,
  backstory: 2000,
  speaking_style: 1000,
  temperament: 200,
  language: 40,
  sample_lines: 10,
  goals: 5,
  rules: 30,
} as const;

export const DEFAULT_FALLBACK_LINE = "Sorry, I can't answer right now. Please try again in a moment.";

export const INDUSTRY_LABELS: Record<Industry, string> = {
  astrology: "Astrology",
  general: "General",
};

export function defaultCompanionValues(): CompanionFormValues {
  return {
    name: "",
    role: "",
    backstory: "",
    speaking_style: "",
    temperament: "",
    language: "",
    sample_lines: [],
    goals: [],
    rules: [],
    industry: "general",
    default_mood: "calm",
    knowledge_tag_id: null,
    privacy_mode: "B",
    fallback_line: DEFAULT_FALLBACK_LINE,
  };
}

/** Trims list items and drops blank rows. */
export function cleanList(items: string[]): string[] {
  return items.map((item) => item.trim()).filter((item) => item.length > 0);
}
