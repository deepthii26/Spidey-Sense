import * as Tooltip from "@radix-ui/react-tooltip";

import { cn } from "../lib/utils";
import type { ActivityRecord, ActivityStatus, Blocker } from "../types";

const steps: Array<{ status: ActivityStatus; label: string }> = [
  { status: "pending", label: "Pending" },
  { status: "working", label: "Working" },
  { status: "done", label: "Done" },
];

const stepIndex: Record<ActivityStatus, number> = {
  pending: 0,
  working: 1,
  done: 2,
};

function blockerExplanation(blocker: Blocker): string {
  if (blocker.type === "same_file") {
    return `${blocker.blocking_teammate} is also editing ${blocker.blocked_file}.`;
  }
  return `${blocker.blocking_teammate} is changing ${blocker.blocking_file}, which ${blocker.blocked_file} depends on.`;
}

function BlockerMarker({ blockers }: { blockers: Blocker[] }) {
  const label = `${blockers.length} ${blockers.length === 1 ? "blocker" : "blockers"}`;
  return (
    <Tooltip.Root>
      <Tooltip.Trigger asChild>
        <button
          type="button"
          aria-label={`${label}. Show blocker details.`}
          className="inline-flex min-h-8 items-center gap-1.5 rounded-full border border-red-200 bg-red-50 px-2.5 py-1 text-xs font-semibold text-red-700 outline-none hover:bg-red-100 focus-visible:ring-2 focus-visible:ring-red-600 focus-visible:ring-offset-2"
        >
          <svg aria-hidden="true" viewBox="0 0 20 20" className="size-3.5 fill-current">
            <path d="M10 2.5a7.5 7.5 0 1 0 0 15 7.5 7.5 0 0 0 0-15Zm.8 11.25H9.2v-1.6h1.6v1.6Zm0-3.05H9.2V6.25h1.6v4.45Z" />
          </svg>
          {label}
        </button>
      </Tooltip.Trigger>
      <Tooltip.Portal>
        <Tooltip.Content
          sideOffset={8}
          className="z-50 max-w-80 rounded-lg bg-slate-950 px-3 py-2 text-xs leading-5 text-pretty text-white shadow-lg"
        >
          <ul className="space-y-1.5">
            {blockers.map((blocker) => (
              <li key={`${blocker.blocking_teammate}-${blocker.blocking_file}`}>
                {blockerExplanation(blocker)}
              </li>
            ))}
          </ul>
          <Tooltip.Arrow className="fill-slate-950" />
        </Tooltip.Content>
      </Tooltip.Portal>
    </Tooltip.Root>
  );
}

function nodeClasses(index: number, current: number, blocked: boolean, status: ActivityStatus) {
  if (blocked && index === current) return "border-red-600 bg-red-600 text-white";
  if (status === "done" && index <= current) return "border-emerald-600 bg-emerald-600 text-white";
  if (index === current) return "border-blue-600 bg-blue-600 text-white";
  if (index < current) return "border-slate-700 bg-slate-700 text-white";
  return "border-slate-300 bg-white text-slate-400";
}

export function StatusPath({
  activity,
  blockers,
}: {
  activity: ActivityRecord;
  blockers: Blocker[];
}) {
  const current = stepIndex[activity.status];
  const blocked = blockers.length > 0;

  return (
    <div className="mt-6">
      <div className="mb-3 flex min-h-8 items-center justify-between gap-3">
        <p className="text-xs font-medium text-slate-500">Delivery path</p>
        {blocked ? <BlockerMarker blockers={blockers} /> : null}
      </div>
      <ol className="grid grid-cols-3" aria-label={`${activity.teammate} delivery progress`}>
        {steps.map((step, index) => (
          <li key={step.status} className="relative flex flex-col items-center gap-2">
            {index > 0 ? (
              <span
                aria-hidden="true"
                className={cn(
                  "absolute right-1/2 top-3.5 h-1 w-full",
                  index <= current ? "bg-slate-700" : "bg-slate-200",
                  activity.status === "done" && index <= current && "bg-emerald-600",
                  blocked && index === current && "bg-red-600",
                )}
              />
            ) : null}
            <span
              className={cn(
                "relative z-10 grid size-8 place-items-center rounded-full border-2 text-xs font-bold",
                nodeClasses(index, current, blocked, activity.status),
              )}
              aria-current={index === current ? "step" : undefined}
            >
              {index < current || activity.status === "done" ? (
                <svg aria-hidden="true" viewBox="0 0 20 20" className="size-4 fill-current">
                  <path d="m7.8 14.4-4-4 1.4-1.4 2.6 2.6 7-7L16.2 6l-8.4 8.4Z" />
                </svg>
              ) : (
                index + 1
              )}
            </span>
            <span
              className={cn(
                "text-xs font-medium",
                index === current ? "text-slate-950" : "text-slate-500",
                blocked && index === current && "text-red-700",
              )}
            >
              {step.label}
            </span>
          </li>
        ))}
      </ol>
    </div>
  );
}
