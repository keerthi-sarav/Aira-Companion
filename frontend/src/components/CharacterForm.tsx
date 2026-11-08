"use client";

import { FormEvent, useState } from "react";
import { errorText } from "@/lib/api";
import { INDUSTRY_LABELS, LIMITS, cleanList, pickFormValues } from "@/lib/companion";
import type { CompanionFormValues, Industry, Mood, PrivacyMode } from "@/lib/types";
import { MOOD_META, MOODS } from "./MoodBadge";

type FieldKey = keyof CompanionFormValues;
type FieldErrors = Partial<Record<FieldKey, string>>;

interface CharacterFormProps {
  initial: CompanionFormValues;
  submitLabel: string;
  onSubmit: (values: CompanionFormValues) => Promise<void>;
  /** Blocks submit while something else (for example a status change) is in flight. */
  disabled?: boolean;
}

function lengthError(value: string, max: number): string | undefined {
  return value.length > max ? `Maximum ${max} characters.` : undefined;
}

function listError(items: string[], max: number, itemMax: number): string | undefined {
  const cleaned = cleanList(items);
  if (cleaned.length > max) return `At most ${max} items.`;
  if (cleaned.some((item) => item.length > itemMax)) return `Each item can be at most ${itemMax} characters.`;
  return undefined;
}

function validate(v: CompanionFormValues): FieldErrors {
  const all: FieldErrors = {
    name: v.name.trim() ? lengthError(v.name, LIMITS.name) : "Name is required.",
    role: lengthError(v.role, LIMITS.role),
    backstory: lengthError(v.backstory, LIMITS.backstory),
    speaking_style: lengthError(v.speaking_style, LIMITS.speaking_style),
    temperament: lengthError(v.temperament, LIMITS.temperament),
    language: lengthError(v.language, LIMITS.language),
    sample_lines: listError(v.sample_lines, LIMITS.sample_lines, LIMITS.list_item),
    goals: listError(v.goals, LIMITS.goals, LIMITS.list_item),
    rules: listError(v.rules, LIMITS.rules, LIMITS.list_item),
    knowledge_tag_id: lengthError((v.knowledge_tag_id ?? "").trim(), LIMITS.knowledge_tag_id),
    fallback_line: lengthError(v.fallback_line, LIMITS.fallback_line),
  };
  return Object.fromEntries(
    Object.entries(all).filter(([, message]) => Boolean(message)),
  ) as FieldErrors;
}

/**
 * Builds the request body from the whitelisted card fields only (see pickFormValues).
 * Trims names and list rows and maps an empty knowledge tag to null.
 */
function normalize(v: CompanionFormValues): CompanionFormValues {
  const picked = pickFormValues(v);
  const tag = picked.knowledge_tag_id?.trim() ?? "";
  return {
    ...picked,
    name: picked.name.trim(),
    sample_lines: cleanList(picked.sample_lines),
    goals: cleanList(picked.goals),
    rules: cleanList(picked.rules),
    knowledge_tag_id: tag || null,
  };
}

function FieldFooter({ error, hint, count }: { error?: string; hint?: string; count?: string }) {
  if (!error && !hint && !count) return null;
  return (
    <div className="mt-1 flex justify-between gap-3 text-xs">
      <span className={error ? "text-red-600" : "text-neutral-500"}>{error ?? hint}</span>
      {count ? <span className="shrink-0 text-neutral-400">{count}</span> : null}
    </div>
  );
}

function TextField({
  id,
  label,
  value,
  onChange,
  max,
  placeholder,
  hint,
  error,
  multiline = false,
  rows = 3,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  max?: number;
  placeholder?: string;
  hint?: string;
  error?: string;
  multiline?: boolean;
  rows?: number;
}) {
  const count = max ? `${value.length}/${max}` : undefined;
  return (
    <div>
      <label htmlFor={id} className="label">
        {label}
      </label>
      {multiline ? (
        <textarea
          id={id}
          rows={rows}
          className="input"
          value={value}
          maxLength={max}
          placeholder={placeholder}
          onChange={(e) => onChange(e.target.value)}
        />
      ) : (
        <input
          id={id}
          type="text"
          className="input"
          value={value}
          maxLength={max}
          placeholder={placeholder}
          onChange={(e) => onChange(e.target.value)}
        />
      )}
      <FieldFooter error={error} hint={hint} count={count} />
    </div>
  );
}

function SelectField<T extends string>({
  id,
  label,
  value,
  options,
  onChange,
  hint,
}: {
  id: string;
  label: string;
  value: T;
  options: { value: T; label: string }[];
  onChange: (value: T) => void;
  hint?: string;
}) {
  return (
    <div>
      <label htmlFor={id} className="label">
        {label}
      </label>
      <select id={id} className="input" value={value} onChange={(e) => onChange(e.target.value as T)}>
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      <FieldFooter hint={hint} />
    </div>
  );
}

function ListField({
  label,
  values,
  max,
  itemMax,
  placeholder,
  hint,
  error,
  onChange,
}: {
  label: string;
  values: string[];
  max: number;
  itemMax: number;
  placeholder?: string;
  hint?: string;
  error?: string;
  onChange: (values: string[]) => void;
}) {
  const full = values.length >= max;
  return (
    <div>
      <div className="flex items-baseline justify-between">
        <span className="label">{label}</span>
        <span className="text-xs text-neutral-500">
          {values.length}/{max}
        </span>
      </div>
      <div className="space-y-2">
        {values.map((item, index) => (
          <div key={index} className="flex gap-2">
            <input
              type="text"
              aria-label={`${label} ${index + 1}`}
              className="input"
              value={item}
              maxLength={itemMax}
              placeholder={placeholder}
              onChange={(e) => {
                const next = [...values];
                next[index] = e.target.value;
                onChange(next);
              }}
            />
            <button
              type="button"
              className="btn"
              aria-label={`Remove ${label} ${index + 1}`}
              onClick={() => onChange(values.filter((_, i) => i !== index))}
            >
              Remove
            </button>
          </div>
        ))}
      </div>
      <button
        type="button"
        className="btn mt-2"
        disabled={full}
        onClick={() => onChange([...values, ""])}
      >
        Add
      </button>
      <FieldFooter error={error} hint={hint ?? (full ? `Limit of ${max} reached.` : undefined)} />
    </div>
  );
}

export default function CharacterForm({ initial, submitLabel, onSubmit, disabled = false }: CharacterFormProps) {
  const [values, setValues] = useState<CompanionFormValues>(initial);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  function set<K extends FieldKey>(key: K, value: CompanionFormValues[K]) {
    setValues((prev) => ({ ...prev, [key]: value }));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError(null);
    const found = validate(values);
    setErrors(found);
    if (Object.keys(found).length > 0) {
      setFormError("Please fix the highlighted fields.");
      return;
    }
    setBusy(true);
    try {
      await onSubmit(normalize(values));
    } catch (err) {
      setFormError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  const industryOptions: { value: Industry; label: string }[] = (
    Object.keys(INDUSTRY_LABELS) as Industry[]
  ).map((value) => ({ value, label: INDUSTRY_LABELS[value] }));

  const moodOptions: { value: Mood; label: string }[] = MOODS.map((value) => ({
    value,
    label: `${MOOD_META[value].emoji} ${MOOD_META[value].label}`,
  }));

  const privacyOptions: { value: PrivacyMode; label: string }[] = [
    { value: "B", label: "B: stats only (default)" },
    { value: "A", label: "A: business can read chats" },
  ];

  return (
    <form onSubmit={handleSubmit} noValidate className="space-y-8">
      <fieldset className="space-y-4">
        <legend className="section-title">Identity</legend>
        <div className="grid gap-4 sm:grid-cols-2">
          <TextField
            id="name"
            label="Name"
            value={values.name}
            max={LIMITS.name}
            placeholder="Jothidar AI"
            error={errors.name}
            onChange={(v) => set("name", v)}
          />
          <TextField
            id="language"
            label="Language"
            value={values.language}
            max={LIMITS.language}
            placeholder="Tanglish"
            error={errors.language}
            onChange={(v) => set("language", v)}
          />
          <TextField
            id="role"
            label="Role"
            value={values.role}
            max={LIMITS.role}
            placeholder="Astrologer"
            error={errors.role}
            onChange={(v) => set("role", v)}
          />
          <TextField
            id="temperament"
            label="Temperament"
            value={values.temperament}
            max={LIMITS.temperament}
            placeholder="Patient, gentle, a little playful"
            error={errors.temperament}
            onChange={(v) => set("temperament", v)}
          />
        </div>
      </fieldset>

      <fieldset className="space-y-4">
        <legend className="section-title">Persona</legend>
        <TextField
          id="backstory"
          label="Backstory"
          value={values.backstory}
          max={LIMITS.backstory}
          rows={5}
          multiline
          error={errors.backstory}
          onChange={(v) => set("backstory", v)}
        />
        <TextField
          id="speaking_style"
          label="Speaking style"
          value={values.speaking_style}
          max={LIMITS.speaking_style}
          rows={3}
          multiline
          error={errors.speaking_style}
          onChange={(v) => set("speaking_style", v)}
        />
      </fieldset>

      <fieldset className="space-y-4">
        <legend className="section-title">Examples, goals and rules</legend>
        <ListField
          label="Sample lines"
          values={values.sample_lines}
          max={LIMITS.sample_lines}
          itemMax={LIMITS.list_item}
          placeholder="A line the character might say"
          hint="Used as tone examples only, never as scripts."
          error={errors.sample_lines}
          onChange={(v) => set("sample_lines", v)}
        />
        <ListField
          label="Goals (in order)"
          values={values.goals}
          max={LIMITS.goals}
          itemMax={LIMITS.list_item}
          placeholder="A goal for the conversation"
          error={errors.goals}
          onChange={(v) => set("goals", v)}
        />
        <ListField
          label="Rules"
          values={values.rules}
          max={LIMITS.rules}
          itemMax={LIMITS.list_item}
          placeholder="A rule the character must follow"
          error={errors.rules}
          onChange={(v) => set("rules", v)}
        />
      </fieldset>

      <fieldset className="space-y-4">
        <legend className="section-title">Behaviour</legend>
        <div className="grid gap-4 sm:grid-cols-2">
          <SelectField
            id="industry"
            label="Industry"
            value={values.industry}
            options={industryOptions}
            onChange={(v) => set("industry", v)}
            hint="Adds industry safety rules to the prompt."
          />
          <SelectField
            id="default_mood"
            label="Default mood"
            value={values.default_mood}
            options={moodOptions}
            onChange={(v) => set("default_mood", v)}
            hint="Where a new person's conversation starts."
          />
        </div>
        <SelectField
          id="privacy_mode"
          label="Privacy mode"
          value={values.privacy_mode}
          options={privacyOptions}
          onChange={(v) => set("privacy_mode", v)}
          hint="A: the business can read chat transcripts. B: the business sees aggregate stats only, not message text."
        />
        <TextField
          id="knowledge_tag_id"
          label="Knowledge tag (optional)"
          value={values.knowledge_tag_id ?? ""}
          max={LIMITS.knowledge_tag_id}
          placeholder="Leave empty to use untagged books only"
          hint="The character reads books with this tag plus untagged books."
          error={errors.knowledge_tag_id}
          onChange={(v) => set("knowledge_tag_id", v)}
        />
        <TextField
          id="fallback_line"
          label="Fallback line"
          value={values.fallback_line}
          max={LIMITS.fallback_line}
          rows={2}
          multiline
          hint="Shown to the person when the model fails."
          error={errors.fallback_line}
          onChange={(v) => set("fallback_line", v)}
        />
      </fieldset>

      <div className="flex flex-wrap items-center gap-3">
        <button type="submit" className="btn btn-primary" disabled={busy || disabled}>
          {busy ? "Saving..." : submitLabel}
        </button>
        {formError ? (
          <span role="alert" className="text-sm text-red-600">
            {formError}
          </span>
        ) : null}
      </div>
    </form>
  );
}
