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
  /** Per item in sample_lines, goals and rules. */
  list_item: 500,
  fallback_line: 500,
  knowledge_tag_id: 64,
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
    language: "English",
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

/**
 * The only fields the character form ever sends. Status, id, tenant_id and timestamps are
 * deliberately absent, so a PATCH cannot carry a stale copy of them back to the server.
 */
export function pickFormValues(source: CompanionFormValues): CompanionFormValues {
  return {
    name: source.name,
    role: source.role,
    backstory: source.backstory,
    speaking_style: source.speaking_style,
    temperament: source.temperament,
    language: source.language,
    sample_lines: source.sample_lines,
    goals: source.goals,
    rules: source.rules,
    industry: source.industry,
    default_mood: source.default_mood,
    knowledge_tag_id: source.knowledge_tag_id,
    privacy_mode: source.privacy_mode,
    fallback_line: source.fallback_line,
  };
}
