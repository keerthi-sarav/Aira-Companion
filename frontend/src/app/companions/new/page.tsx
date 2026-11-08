"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import CharacterForm from "@/components/CharacterForm";
import { api } from "@/lib/api";
import { defaultCompanionValues } from "@/lib/companion";

const INITIAL_VALUES = defaultCompanionValues();

export default function NewCompanionPage() {
  const router = useRouter();

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">New character</h1>
          <p className="hint">Define the card. You can test-chat it right after creating it.</p>
        </div>
        <Link href="/" className="btn">
          Cancel
        </Link>
      </div>

      <section className="card">
        <CharacterForm
          initial={INITIAL_VALUES}
          submitLabel="Create character"
          onSubmit={async (values) => {
            const created = await api.createCompanion(values);
            router.push(`/companions/${created.id}`);
          }}
        />
      </section>
    </div>
  );
}
