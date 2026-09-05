import * as Tooltip from "@radix-ui/react-tooltip";
import { lazy, Suspense } from "react";

import { MissionControl } from "./components/MissionControl";
import { StatusPath } from "./components/StatusPath";
import { cn, formatTimestamp, repositoryName } from "./lib/utils";
import type {
  ActivityRecord,
  ActivityUpdate,
  Blocker,
  DashboardPayload,
  DirectiveInput,
} from "./types";

const DependencyWorld = lazy(() =>
  import("./components/DependencyWorld").then((module) => ({ default: module.DependencyWorld })),
);

const statusLabels = {
  pending: "Queued",
  working: "On mission",
  done: "Secured",
};

const statusBadgeClasses = {
  pending: "border-amber-400/25 bg-amber-400/10 text-amber-300",
  working: "border-blue-400/30 bg-blue-400/10 text-blue-300",
  done: "border-emerald-400/25 bg-emerald-400/10 text-emerald-300",
};

function initials(value: string): string {
  return value
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("");
}

function WebMark() {
  return (
    <svg aria-hidden="true" viewBox="0 0 44 44" className="size-11">
      <circle cx="22" cy="22" r="19" fill="#071020" stroke="#2f7fff" strokeWidth="1" />
      <path
        d="M22 4v36M4 22h36M9.3 9.3l25.4 25.4M34.7 9.3 9.3 34.7M22 10c6.6 0 12 5.4 12 12s-5.4 12-12 12-12-5.4-12-12 5.4-12 12-12Zm0 6a6 6 0 1 1 0 12 6 6 0 0 1 0-12Z"
        fill="none"
        stroke="#8bb6ff"
        strokeOpacity=".72"
        strokeWidth=".75"
      />
      <circle cx="22" cy="22" r="3" fill="#e42d55" />
    </svg>
  );
}

function TeammateTrack({ activity, blockers }: { activity: ActivityRecord; blockers: Blocker[] }) {
  const blocked = blockers.length > 0;
  return (
    <article className={cn("web-panel p-5", blocked && "border-rose-500/35")}>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex min-w-0 items-center gap-3">
          <div
            className={cn(
              "grid size-11 shrink-0 place-items-center rounded-lg border bg-[#081224] font-mono text-sm font-black text-blue-100",
              blocked ? "border-rose-400/50 text-rose-200" : "border-blue-400/25",
            )}
          >
            {initials(activity.teammate)}
          </div>
          <div className="min-w-0">
            <p className="web-label">Web runner</p>
            <h3 className="mt-0.5 truncate text-base font-semibold text-white">{activity.teammate}</h3>
            <p className="mt-0.5 text-xs text-slate-500">
              Pulse <span className="tabular-nums">{formatTimestamp(activity.updated_at)}</span>
            </p>
          </div>
        </div>
        <span
          className={cn(
            "rounded-full border px-2.5 py-1 font-mono text-[10px] font-bold uppercase tracking-wider",
            statusBadgeClasses[activity.status],
          )}
        >
          {statusLabels[activity.status]}
        </span>
      </div>

      <StatusPath activity={activity} blockers={blockers} />

      <div className="mt-6 border-t border-blue-300/10 pt-4">
        <p className="mb-2 font-mono text-[10px] font-semibold uppercase tracking-wider text-slate-500">
          {activity.files.length} {activity.files.length === 1 ? "node" : "nodes"} in range
        </p>
        <div className="flex flex-wrap gap-2">
          {activity.files.map((file) => (
            <code
              key={file}
              title={file}
              className="max-w-full truncate rounded-md border border-blue-300/10 bg-blue-300/5 px-2 py-1 text-xs text-blue-100/75"
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
    <li className="rounded-lg border border-rose-400/25 bg-rose-500/8 p-3">
      <div className="flex items-start gap-2.5">
        <div className="signal-pulse mt-0.5 grid size-6 shrink-0 place-items-center rounded-full bg-[#e12b53] text-white">
          <svg aria-hidden="true" viewBox="0 0 20 20" className="size-3.5 fill-current">
            <path d="M10 2.5a7.5 7.5 0 1 0 0 15 7.5 7.5 0 0 0 0-15Zm.8 11.25H9.2v-1.6h1.6v1.6Zm0-3.05H9.2V6.25h1.6v4.45Z" />
          </svg>
        </div>
        <div className="min-w-0">
          <p className="text-sm font-semibold text-rose-100">{blocker.blocked_teammate} is blocked</p>
          <p className="mt-1 text-xs leading-5 text-pretty text-rose-200/70">
            {sameFile
              ? `${blocker.blocking_teammate} is editing the same web node.`
              : `${blocker.blocking_teammate} owns an upstream strand.`}
          </p>
          <code className="mt-2 block truncate text-xs text-rose-300" title={blocker.blocking_file}>
            {blocker.blocking_file}
          </code>
        </div>
      </div>
    </li>
  );
}

function Metric({ label, value, danger = false }: { label: string; value: number; danger?: boolean }) {
  return (
    <div className="web-panel px-4 py-3.5">
      <p className={cn("web-label", danger && "text-rose-400")}>{label}</p>
      <p className={cn("mt-1 text-2xl font-black tabular-nums text-white", danger && "text-rose-300")}>
        {String(value).padStart(2, "0")}
      </p>
    </div>
  );
}

export function DashboardView({
  data,
  refreshing,
  onRefresh,
  mutationPending,
  onUpdateActivity,
  onCreateDirective,
}: {
  data: DashboardPayload;
  refreshing: boolean;
  onRefresh: () => void;
  mutationPending: boolean;
  onUpdateActivity: (input: ActivityUpdate) => Promise<void>;
  onCreateDirective: (input: DirectiveInput) => Promise<void>;
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
      <div className="spidey-shell min-h-dvh bg-[#030711] text-slate-100">
        <header className="border-b border-blue-300/10 bg-[#040a16]/90 backdrop-blur-xl">
          <div className="mx-auto flex max-w-[94rem] flex-wrap items-center justify-between gap-4 px-4 py-4 sm:px-6 lg:px-8">
            <div className="flex items-center gap-3">
              <WebMark />
              <div>
                <div className="flex items-center gap-2">
                  <span className="signal-pulse size-1.5 rounded-full bg-emerald-400 text-emerald-400" />
                  <p className="web-label text-emerald-400">Sense online // 3s pulse</p>
                </div>
                <h1 className="mt-0.5 text-xl font-black uppercase tracking-[0.08em] text-white text-balance">
                  Spidey Sense
                </h1>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <div className="hidden text-right sm:block">
                <p className="max-w-72 truncate font-mono text-xs font-semibold text-blue-100" title={data.repository}>
                  {repositoryName(data.repository)} // {data.live.git.branch}
                </p>
                <p className="mt-1 font-mono text-[10px] uppercase tracking-wider text-slate-500 tabular-nums">
                  Web pulse {formatTimestamp(data.generated_at)}
                </p>
              </div>
              <button
                type="button"
                onClick={onRefresh}
                disabled={refreshing}
                className="inline-flex min-h-10 items-center gap-2 rounded-md border border-blue-400/40 bg-blue-500/15 px-3.5 py-2 font-mono text-[10px] font-bold uppercase tracking-wider text-blue-100 outline-none hover:bg-blue-500/25 focus-visible:ring-2 focus-visible:ring-blue-400 disabled:cursor-wait disabled:opacity-60"
              >
                <svg aria-hidden="true" viewBox="0 0 20 20" className="size-4 fill-current">
                  <path d="M15.2 4.8A7.3 7.3 0 1 0 17.3 10h-2a5.3 5.3 0 1 1-1.5-3.7L11 9h7V2l-2.8 2.8Z" />
                </svg>
                {refreshing ? "Scanning…" : "Scan now"}
              </button>
            </div>
          </div>
        </header>

        <main className="mx-auto max-w-[94rem] px-4 py-6 sm:px-6 lg:px-8">
          <section aria-labelledby="overview-heading">
            <h2 id="overview-heading" className="sr-only">Live web overview</h2>
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
              <Metric label="Web runners" value={teammates.length} />
              <Metric label="Live missions" value={workingCount} />
              <Metric label="Danger signals" value={blockedTeammates} danger={blockedTeammates > 0} />
              <Metric label="Nodes secured" value={doneCount} />
            </div>
          </section>

          <div className="mt-5 grid items-start gap-5 xl:grid-cols-[minmax(0,1fr)_23rem]">
            <Suspense
              fallback={
                <section className="web-panel grid min-h-[39rem] place-items-center font-mono text-xs uppercase tracking-widest text-blue-300/60">
                  Weaving the dependency web…
                </section>
              }
            >
              <DependencyWorld data={data} />
            </Suspense>
            <MissionControl
              data={data}
              pending={mutationPending}
              onUpdateActivity={onUpdateActivity}
              onCreateDirective={onCreateDirective}
            />
          </div>

          <div className="mt-8 grid gap-8 lg:grid-cols-[minmax(0,1fr)_21rem]">
            <section aria-labelledby="tracks-heading">
              <div className="mb-4 flex items-end justify-between gap-4">
                <div>
                  <p className="web-label">Team coordination</p>
                  <h2 id="tracks-heading" className="mt-1 text-lg font-bold text-white text-balance">
                    Mission pathways
                  </h2>
                  <p className="mt-1 text-sm text-pretty text-slate-400">
                    Every runner moves from queued to active work to a secured node.
                  </p>
                </div>
                <p className="hidden font-mono text-[10px] uppercase tracking-wider text-slate-500 tabular-nums sm:block">
                  {graphStats.nodes} nodes · {graphStats.edges} {graphStats.edges === 1 ? "strand" : "strands"}
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
                <div className="web-panel border-dashed p-8 text-center">
                  <h3 className="font-semibold text-white text-balance">No runner activity yet</h3>
                  <p className="mx-auto mt-2 max-w-md text-sm text-pretty text-slate-400">
                    Add the first queued or active mission to create a pathway.
                  </p>
                  <code className="mt-4 inline-block rounded-md border border-blue-300/10 bg-blue-300/5 px-3 py-2 text-xs text-blue-200">
                    python -m spidey_sense.activity set alice working src/app.ts
                  </code>
                </div>
              )}
            </section>

            <aside className="space-y-5" aria-label="Coordination details">
              <section className="web-panel p-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="web-label text-rose-400">Early warning</p>
                    <h2 className="mt-1 font-bold text-white text-balance">Danger signals</h2>
                  </div>
                  <span className="rounded-full border border-rose-400/25 bg-rose-400/10 px-2 py-0.5 font-mono text-xs font-bold text-rose-300 tabular-nums">
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
                  <div className="mt-4 rounded-lg border border-emerald-400/15 bg-emerald-400/8 p-3">
                    <p className="text-sm font-semibold text-emerald-200">The web is clear</p>
                    <p className="mt-1 text-xs text-pretty text-emerald-200/60">
                      No active file ownership tangles detected.
                    </p>
                  </div>
                )}
              </section>

              <section className="web-panel p-4">
                <p className="web-label">GitHub timeline</p>
                <h2 className="mt-1 font-bold text-white text-balance">Latest merge</h2>
                {recentPull ? (
                  <div className="mt-3">
                    <a
                      href={recentPull.html_url}
                      target="_blank"
                      rel="noreferrer"
                      className="line-clamp-2 text-sm font-semibold text-blue-300 underline decoration-blue-400/30 underline-offset-4 hover:text-blue-100"
                    >
                      #{recentPull.number} {recentPull.title}
                    </a>
                    <p className="mt-2 text-xs text-slate-500">
                      by {recentPull.author_login} · {recentPull.files.length} nodes
                    </p>
                    <p className="mt-1 text-xs text-slate-500 tabular-nums">
                      {formatTimestamp(recentPull.merged_at)}
                    </p>
                  </div>
                ) : (
                  <div className="mt-3">
                    <p className="text-sm text-pretty text-slate-400">No GitHub sync result attached.</p>
                    <p className="mt-2 text-xs text-pretty text-slate-500">
                      Run the merge sync and attach its output to the dashboard server.
                    </p>
                  </div>
                )}
              </section>

              <section className="web-panel p-4">
                <p className="web-label">Structural scan</p>
                <h2 className="mt-1 font-bold text-white text-balance">Web integrity</h2>
                <dl className="mt-3 grid grid-cols-3 gap-2 text-center">
                  {[
                    ["Nodes", graphStats.nodes],
                    ["Strands", graphStats.edges],
                    ["Notes", graphStats.diagnostics],
                  ].map(([label, value]) => (
                    <div key={label} className="rounded-md border border-blue-300/10 bg-blue-300/5 py-2">
                      <dt className="font-mono text-[9px] uppercase tracking-wider text-slate-500">{label}</dt>
                      <dd className="mt-1 font-bold text-white tabular-nums">{value}</dd>
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
