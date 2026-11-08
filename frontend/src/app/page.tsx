"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import StatusBadge from "@/components/StatusBadge";
import { api, errorText } from "@/lib/api";
import { INDUSTRY_LABELS } from "@/lib/companion";
import type { CompanionRead } from "@/lib/types";

export default function CompanionListPage() {
  const [companions, setCompanions] = useState<CompanionRead[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      setCompanions(await api.listCompanions());
    } catch (err) {
      setError(errorText(err));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Characters</h1>
          <p className="hint">AI characters for this tenant.</p>
        </div>
        <Link href="/companions/new" className="btn btn-primary">
          New character
        </Link>
      </div>

      {error ? (
        <div role="alert" className="card space-y-3 border-red-200 bg-red-50">
          <p className="text-sm text-red-700">{error}</p>
          <button type="button" className="btn" onClick={() => void load()}>
            Retry
          </button>
        </div>
      ) : null}

      {!error && companions === null ? (
        <div className="card space-y-3" aria-busy="true">
          <p className="text-sm text-neutral-500">Loading characters...</p>
          <div className="h-4 w-1/3 animate-pulse rounded bg-neutral-200" />
          <div className="h-4 w-1/2 animate-pulse rounded bg-neutral-200" />
        </div>
      ) : null}

      {!error && companions !== null && companions.length === 0 ? (
        <div className="card flex flex-col items-start gap-3">
          <p className="text-sm text-neutral-700">No characters yet.</p>
          <p className="hint">Create one, then test-chat it from its page.</p>
          <Link href="/companions/new" className="btn btn-primary">
            Create your first character
          </Link>
        </div>
      ) : null}

      {companions !== null && companions.length > 0 ? (
        <ul className="card divide-y divide-neutral-200 p-0">
          {companions.map((c) => (
            <li key={c.id}>
              <Link
                href={`/companions/${c.id}`}
                className="flex flex-wrap items-center justify-between gap-3 px-5 py-4 hover:bg-neutral-50"
              >
                <div className="min-w-0">
                  <p className="truncate font-medium text-neutral-900">{c.name}</p>
                  <p className="hint truncate">
                    {c.role || "No role set"}
                    {c.language ? ` · ${c.language}` : ""}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <span className="rounded-full bg-neutral-100 px-2 py-0.5 text-xs text-neutral-700">
                    {INDUSTRY_LABELS[c.industry]}
                  </span>
                  <StatusBadge status={c.status} />
                </div>
              </Link>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
