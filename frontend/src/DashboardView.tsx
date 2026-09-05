import * as Tooltip from "@radix-ui/react-tooltip";

import { StatusPath } from "./components/StatusPath";
import { cn, formatTimestamp, repositoryName } from "./lib/utils";
import type { ActivityRecord, Blocker, DashboardPayload } from "./types";

const statusLabels = {
  pending: "Pending",
  working: "Working",
  done: "Done",
};

const statusBadgeClasses = {
  pending: "border-amber-200 bg-amber-50 text-amber-800",
  working: "border-blue-200 bg-blue-50 text-blue-800",
  done: "border-emerald-200 bg-emerald-50 text-emerald-800",
};

function initials(value: string): string {
  return value
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("");
}

function TeammateTrack({
  activity,
  blockers,
}: {
  activity: ActivityRecord;
  blockers: Blocker[];
}) {
  return (
    <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex min-w-0 items-center gap-3">
          <div className="grid size-11 shrink-0 place-items-center rounded-full bg-slate-900 text-sm font-bold text-white">
            {initials(activity.teammate)}
          </div>
          <div className="min-w-0">
            <h3 className="truncate text-base font-semibold text-slate-950">{activity.teammate}</h3>
            <p className="mt-0.5 text-xs text-slate-500">
              Updated <span className="tabular-nums">{formatTimestamp(activity.updated_at)}</span>
            </p>
          </div>
        </div>
        <span
          className={cn(
            "rounded-full border px-2.5 py-1 text-xs font-semibold",
            statusBadgeClasses[activity.status],
          )}
        >
          {statusLabels[activity.status]}
        </span>
      </div>

      <StatusPath activity={activity} blockers={blockers} />

      <div className="mt-6 border-t border-slate-100 pt-4">
        <p className="mb-2 text-xs font-medium text-slate-500">
          {activity.files.length} {activity.files.length === 1 ? "file" : "files"} in scope
        </p>
        <div className="flex flex-wrap gap-2">
          {activity.files.map((file) => (
            <code
              key={file}
              title={file}
              className="max-w-full truncate rounded-md bg-slate-100 px-2 py-1 text-xs text-slate-700"
            >
              {file}
            </code>
          ))}
        </div>
      </div>
    </article>
  );
}

function AlertCard({ blocker }: { blocker: Blocker }) {
  const sameFile = blocker.type === "same_file";
  return (
    <li className="rounded-xl border border-red-200 bg-red-50 p-3">
      <div className="flex items-start gap-2.5">
        <div className="mt-0.5 grid size-6 shrink-0 place-items-center rounded-full bg-red-600 text-white">
          <svg aria-hidden="true" viewBox="0 0 20 20" className="size-3.5 fill-current">
            <path d="M10 2.5a7.5 7.5 0 1 0 0 15 7.5 7.5 0 0 0 0-15Zm.8 11.25H9.2v-1.6h1.6v1.6Zm0-3.05H9.2V6.25h1.6v4.45Z" />
          </svg>
        </div>
        <div className="min-w-0">
          <p className="text-sm font-semibold text-red-950">
            {blocker.blocked_teammate} is blocked
          </p>
          <p className="mt-1 text-xs leading-5 text-pretty text-red-800">
            {sameFile
              ? `${blocker.blocking_teammate} is editing the same file.`
              : `${blocker.blocking_teammate} owns an upstream dependency.`}
          </p>
          <code className="mt-2 block truncate text-xs text-red-700" title={blocker.blocking_file}>
            {blocker.blocking_file}
          </code>
        </div>
      </div>
    </li>
  );
}

export function DashboardView({
  data,
  refreshing,
  onRefresh,
}: {
  data: DashboardPayload;
  refreshing: boolean;
  onRefresh: () => void;
}) {
  const teammates = Object.values(data.activity.teammates).sort((left, right) =>
    left.teammate.localeCompare(right.teammate),
  );
  const activeBlockers = data.blockers;
  const blockedTeammates = new Set(activeBlockers.map((blocker) => blocker.blocked_teammate)).size;
  const workingCount = teammates.filter((teammate) => teammate.status === "working").length;
  const doneCount = teammates.filter((teammate) => teammate.status === "done").length;
  const graphStats = data.graph.stats;
  const recentPull = data.github_sync?.merged_pull_requests[0];

  return (
    <Tooltip.Provider delayDuration={150}>
      <div className="min-h-dvh bg-slate-50 text-slate-950">
        <header className="border-b border-slate-200 bg-white">
          <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-4 py-5 sm:px-6 lg:px-8">
            <div className="flex items-center gap-3">
              <div className="relative grid size-10 place-items-center rounded-xl bg-slate-950 text-white">
                <span className="size-4 rounded-full border-2 border-white" />
                <span className="absolute right-2 top-2 size-1.5 rounded-full bg-blue-400" />
              </div>
              <div>
                <p className="text-xs font-semibold text-blue-700">Live coordination</p>
                <h1 className="text-xl font-bold text-balance">Spidey Sense</h1>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <div className="hidden text-right sm:block">
                <p className="max-w-64 truncate text-sm font-medium" title={data.repository}>
                  {repositoryName(data.repository)}
                </p>
                <p className="text-xs text-slate-500 tabular-nums">
                  Snapshot {formatTimestamp(data.generated_at)}
                </p>
              </div>
              <button
                type="button"
                onClick={onRefresh}
                disabled={refreshing}
                className="inline-flex min-h-10 items-center gap-2 rounded-lg bg-blue-600 px-3.5 py-2 text-sm font-semibold text-white shadow-sm outline-none hover:bg-blue-700 focus-visible:ring-2 focus-visible:ring-blue-600 focus-visible:ring-offset-2 disabled:cursor-wait disabled:opacity-60"
              >
                <svg aria-hidden="true" viewBox="0 0 20 20" className="size-4 fill-current">
                  <path d="M15.2 4.8A7.3 7.3 0 1 0 17.3 10h-2a5.3 5.3 0 1 1-1.5-3.7L11 9h7V2l-2.8 2.8Z" />
                </svg>
                {refreshing ? "Refreshing…" : "Refresh"}
              </button>
            </div>
          </div>
        </header>

        <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
          <section aria-labelledby="overview-heading">
            <h2 id="overview-heading" className="sr-only">
              Coordination overview
            </h2>
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
              {[
                ["Teammates", teammates.length],
                ["Working now", workingCount],
                ["Blocked paths", blockedTeammates],
                ["Completed", doneCount],
              ].map(([label, value]) => (
                <div key={label} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                  <p className="text-xs font-medium text-slate-500">{label}</p>
                  <p className="mt-1 text-2xl font-bold tabular-nums">{value}</p>
                </div>
              ))}
            </div>
          </section>

          <div className="mt-8 grid gap-8 lg:grid-cols-[minmax(0,1fr)_20rem]">
            <section aria-labelledby="tracks-heading">
              <div className="mb-4 flex items-end justify-between gap-4">
                <div>
                  <h2 id="tracks-heading" className="text-lg font-bold text-balance">
                    Team pathways
                  </h2>
                  <p className="mt-1 text-sm text-pretty text-slate-600">
                    Work advances from pending to active delivery and completion.
                  </p>
                </div>
                <p className="hidden text-xs text-slate-500 tabular-nums sm:block">
                  {graphStats.nodes} files · {graphStats.edges}{" "}
                  {graphStats.edges === 1 ? "dependency" : "dependencies"}
                </p>
              </div>

              {teammates.length ? (
                <div className="space-y-4">
                  {teammates.map((activity) => (
                    <TeammateTrack
                      key={activity.teammate}
                      activity={activity}
                      blockers={activeBlockers.filter(
                        (blocker) => blocker.blocked_teammate === activity.teammate,
                      )}
                    />
                  ))}
                </div>
              ) : (
                <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-8 text-center">
                  <h3 className="font-semibold text-balance">No teammate activity yet</h3>
                  <p className="mx-auto mt-2 max-w-md text-sm text-pretty text-slate-600">
                    Add the first pending or working activity record to create a pathway.
                  </p>
                  <code className="mt-4 inline-block rounded-md bg-slate-100 px-3 py-2 text-xs text-slate-700">
                    python -m spidey_sense.activity set alice working src/app.ts
                  </code>
                </div>
              )}
            </section>

            <aside className="space-y-5" aria-label="Coordination details">
              <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                <div className="flex items-center justify-between gap-3">
                  <h2 className="font-bold text-balance">Coordination alerts</h2>
                  <span className="rounded-full bg-red-100 px-2 py-0.5 text-xs font-bold text-red-700 tabular-nums">
                    {activeBlockers.length}
                  </span>
                </div>
                {activeBlockers.length ? (
                  <ul className="mt-4 space-y-3">
                    {activeBlockers.map((blocker) => (
                      <AlertCard
                        key={`${blocker.blocking_teammate}-${blocker.blocked_teammate}-${blocker.blocking_file}`}
                        blocker={blocker}
                      />
                    ))}
                  </ul>
                ) : (
                  <div className="mt-4 rounded-xl bg-emerald-50 p-3">
                    <p className="text-sm font-semibold text-emerald-900">No blockers detected</p>
                    <p className="mt-1 text-xs text-pretty text-emerald-700">
                      Active file ownership is clear right now.
                    </p>
                  </div>
                )}
              </section>

              <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                <h2 className="font-bold text-balance">Latest merge</h2>
                {recentPull ? (
                  <div className="mt-3">
                    <a
                      href={recentPull.html_url}
                      target="_blank"
                      rel="noreferrer"
                      className="line-clamp-2 text-sm font-semibold text-blue-700 underline decoration-blue-200 underline-offset-4 hover:text-blue-900"
                    >
                      #{recentPull.number} {recentPull.title}
                    </a>
                    <p className="mt-2 text-xs text-slate-500">
                      by {recentPull.author_login} · {recentPull.files.length} files
                    </p>
                    <p className="mt-1 text-xs text-slate-500 tabular-nums">
                      {formatTimestamp(recentPull.merged_at)}
                    </p>
                  </div>
                ) : (
                  <div className="mt-3">
                    <p className="text-sm text-pretty text-slate-600">No GitHub sync result attached.</p>
                    <p className="mt-2 text-xs text-pretty text-slate-500">
                      Run the Phase 4 sync with an output file, then pass it to the dashboard server.
                    </p>
                  </div>
                )}
              </section>

              <section className="rounded-2xl border border-slate-200 bg-slate-950 p-4 text-white shadow-sm">
                <h2 className="font-bold text-balance">Graph health</h2>
                <dl className="mt-3 grid grid-cols-3 gap-2 text-center">
                  {[
                    ["Files", graphStats.nodes],
                    ["Edges", graphStats.edges],
                    ["Notes", graphStats.diagnostics],
                  ].map(([label, value]) => (
                    <div key={label}>
                      <dt className="text-xs text-slate-400">{label}</dt>
                      <dd className="mt-1 font-bold tabular-nums">{value}</dd>
                    </div>
                  ))}
                </dl>
              </section>
            </aside>
          </div>
        </main>
      </div>
    </Tooltip.Provider>
  );
}
