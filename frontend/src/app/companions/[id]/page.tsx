"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import CharacterForm from "@/components/CharacterForm";
import StatusBadge from "@/components/StatusBadge";
import TestChat from "@/components/TestChat";
import { api, errorText } from "@/lib/api";
import { INDUSTRY_LABELS, pickFormValues } from "@/lib/companion";
import type { CompanionFormValues, CompanionRead, Status } from "@/lib/types";

const STATUS_OPTIONS: { value: Status; help: string }[] = [
  { value: "draft", help: "Only the test chat can reach it." },
  { value: "live", help: "The embedded app can chat with it." },
  { value: "paused", help: "The embedded app is refused (409)." },
];

export default function CompanionDetailPage({ params }: { params: { id: string } }) {
  const { id } = params;
  const router = useRouter();

  const [companion, setCompanion] = useState<CompanionRead | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [statusBusy, setStatusBusy] = useState(false);
  const [statusError, setStatusError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .getCompanion(id)
      .then((c) => {
        if (!cancelled) setCompanion(c);
      })
      .catch((err: unknown) => {
        if (!cancelled) setLoadError(errorText(err));
      });
    return () => {
      cancelled = true;
    };
  }, [id]);

  // Save and status change are serialized: each one's response overwrites the companion state,
  // so the two must never be in flight at once or the slower response would revert the other.
  async function saveCard(values: CompanionFormValues) {
    setNotice(null);
    setSaving(true);
    try {
      const updated = await api.updateCompanion(id, values);
      setCompanion(updated);
      setNotice("Saved.");
    } finally {
      setSaving(false);
    }
  }

  async function changeStatus(status: Status) {
    if (!companion || companion.status === status || saving || statusBusy) return;
    setStatusBusy(true);
    setStatusError(null);
    try {
      setCompanion(await api.updateCompanion(id, { status }));
    } catch (err) {
      setStatusError(errorText(err));
    } finally {
      setStatusBusy(false);
    }
  }

  async function deleteCompanion() {
    if (!companion) return;
    if (!window.confirm(`Delete "${companion.name}"? This cannot be undone.`)) return;
    setDeleting(true);
    setDeleteError(null);
    try {
      await api.deleteCompanion(id);
      router.push("/");
    } catch (err) {
      setDeleteError(errorText(err));
      setDeleting(false);
    }
  }

  if (loadError) {
    return (
      <div className="space-y-4">
        <Link href="/" className="text-sm text-neutral-600 hover:underline">
          Back to characters
        </Link>
        <div role="alert" className="card border-red-200 bg-red-50 text-sm text-red-700">
          {loadError}
        </div>
      </div>
    );
  }

  if (!companion) {
    return <p className="text-sm text-neutral-500">Loading character...</p>;
  }

  const currentHelp = STATUS_OPTIONS.find((o) => o.value === companion.status)?.help;

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <Link href="/" className="text-sm text-neutral-600 hover:underline">
          Back to characters
        </Link>
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-xl font-semibold tracking-tight">{companion.name}</h1>
          <StatusBadge status={companion.status} />
          <span className="rounded-full bg-neutral-100 px-2 py-0.5 text-xs text-neutral-700">
            {INDUSTRY_LABELS[companion.industry]}
          </span>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="space-y-6">
          <section className="card space-y-4">
            <h2 className="section-title">Character</h2>
            {notice ? (
              <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
                {notice}
              </div>
            ) : null}
            <CharacterForm
              initial={pickFormValues(companion)}
              submitLabel="Save changes"
              onSubmit={saveCard}
              disabled={statusBusy}
            />
          </section>

          <section className="card space-y-3">
            <h2 className="section-title">Status</h2>
            <div className="inline-flex rounded-lg border border-neutral-300 p-0.5" role="group" aria-label="Status">
              {STATUS_OPTIONS.map((option) => {
                const active = companion.status === option.value;
                return (
                  <button
                    key={option.value}
                    type="button"
                    aria-pressed={active}
                    disabled={statusBusy || saving}
                    onClick={() => void changeStatus(option.value)}
                    className={`rounded-md px-3 py-1.5 text-sm font-medium capitalize disabled:opacity-50 ${
                      active ? "bg-neutral-900 text-white" : "text-neutral-700 hover:bg-neutral-100"
                    }`}
                  >
                    {option.value}
                  </button>
                );
              })}
            </div>
            {currentHelp ? <p className="hint">{currentHelp}</p> : null}
            {statusError ? (
              <p role="alert" className="text-sm text-red-600">
                {statusError}
              </p>
            ) : null}
          </section>

          <section className="card space-y-3 border-red-200">
            <h2 className="section-title">Delete</h2>
            <p className="hint">Permanently removes this character.</p>
            <button type="button" className="btn btn-danger" onClick={() => void deleteCompanion()} disabled={deleting}>
              {deleting ? "Deleting..." : "Delete character"}
            </button>
            {deleteError ? (
              <p role="alert" className="text-sm text-red-600">
                {deleteError}
              </p>
            ) : null}
          </section>
        </div>

        <div className="lg:sticky lg:top-6 lg:self-start">
          {/* key resets chat state and drops in-flight replies when the route moves to another companion. */}
          <TestChat key={id} companionId={id} />
        </div>
      </div>
    </div>
  );
}
