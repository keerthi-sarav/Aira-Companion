import type { Status } from "@/lib/types";

const STYLES: Record<Status, string> = {
  draft: "bg-neutral-100 text-neutral-700 ring-neutral-300",
  live: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  paused: "bg-amber-50 text-amber-800 ring-amber-200",
};

export default function StatusBadge({ status }: { status: Status }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium capitalize ring-1 ring-inset ${STYLES[status]}`}
    >
      {status}
    </span>
  );
}
