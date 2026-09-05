import { type FormEvent, useMemo, useState } from "react";

import { cn, formatTimestamp } from "../lib/utils";
import type {
  ActivityStatus,
  ActivityUpdate,
  DashboardPayload,
  DirectiveInput,
} from "../types";

const providerColors: Record<string, string> = {
  codex: "bg-emerald-400 text-emerald-400",
  claude: "bg-orange-400 text-orange-400",
  entire: "bg-fuchsia-400 text-fuchsia-400",
};

export function MissionControl({
  data,
  pending,
  onUpdateActivity,
  onCreateDirective,
}: {
  data: DashboardPayload;
  pending: boolean;
  onUpdateActivity: (input: ActivityUpdate) => Promise<void>;
  onCreateDirective: (input: DirectiveInput) => Promise<void>;
}) {
  const teammates = Object.values(data.activity.teammates);
  const [teammate, setTeammate] = useState(teammates[0]?.teammate ?? "");
  const [files, setFiles] = useState(teammates[0]?.files.join(", ") ?? "");
  const [status, setStatus] = useState<ActivityStatus>(teammates[0]?.status ?? "pending");
  const [sessionId, setSessionId] = useState("");
  const [message, setMessage] = useState("");
  const [notice, setNotice] = useState<string | null>(null);

  const selectedSession = useMemo(
    () => data.live.sessions.find((session) => session.id === sessionId),
    [data.live.sessions, sessionId],
  );
  const recentDirectives = data.directives.directives.slice(0, 3);

  async function assignWork(event: FormEvent) {
    event.preventDefault();
    const parsedFiles = files
      .split(/[\n,]/)
      .map((file) => file.trim())
      .filter(Boolean);
    if (!teammate.trim() || !parsedFiles.length) {
      setNotice("Add a teammate and at least one repository-relative file.");
      return;
    }
    try {
      await onUpdateActivity({ teammate: teammate.trim(), files: parsedFiles, status });
      setNotice(`Mission updated for ${teammate.trim()}.`);
    } catch {
      setNotice("The mission update was rejected. Check the error above.");
    }
  }

  async function sendDirective(event: FormEvent) {
    event.preventDefault();
    if (!teammate.trim() || !message.trim()) {
      setNotice("Choose a teammate and write a signal first.");
      return;
    }
    const provider = selectedSession?.provider ?? "inbox";
    try {
      await onCreateDirective({
        teammate: teammate.trim(),
        message: message.trim(),
        provider,
        session_id: selectedSession?.id,
        deliver_now: provider === "codex" && Boolean(selectedSession),
      });
      setMessage("");
      setNotice(
        provider === "codex"
          ? "Signal sent directly to the Codex thread."
          : "Signal queued in the shared runner inbox.",
      );
    } catch {
      setNotice("The signal could not be delivered. Check the error above.");
    }
  }

  return (
    <aside className="space-y-4" aria-label="Live mission control">
      <section className="web-panel p-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="web-label">Agent radar</p>
            <h2 className="mt-1 font-bold text-white text-balance">Web runners</h2>
          </div>
          <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-400/20 bg-emerald-400/10 px-2.5 py-1 font-mono text-[9px] font-bold uppercase tracking-wider text-emerald-300">
            <span className="signal-pulse size-1.5 rounded-full bg-emerald-400 text-emerald-400" />
            Live · 3s
          </span>
        </div>
        <div className="mt-3 space-y-2">
          {data.live.sessions.length ? (
            data.live.sessions.slice(0, 4).map((session) => (
              <button
                key={`${session.provider}-${session.id}`}
                type="button"
                onClick={() => {
                  setSessionId(session.id);
                  if (!teammate) setTeammate(session.name);
                }}
                className={cn(
                  "w-full rounded-lg border p-3 text-left outline-none focus-visible:ring-2 focus-visible:ring-blue-500",
                  sessionId === session.id
                    ? "border-blue-400/60 bg-blue-500/12"
                    : "border-blue-300/10 bg-blue-300/3 hover:border-blue-300/25",
                )}
              >
                <div className="flex items-center justify-between gap-3">
                  <span className="flex items-center gap-2 font-mono text-[10px] font-bold uppercase tracking-wider text-blue-100">
                    <span
                      className={cn(
                        "signal-pulse size-1.5 rounded-full",
                        providerColors[session.provider] ?? "bg-slate-400 text-slate-400",
                      )}
                    />
                    {session.name} · {session.provider}
                  </span>
                  <span className="font-mono text-[9px] font-semibold uppercase text-slate-500">
                    {session.status}
                  </span>
                </div>
                <p className="mt-1.5 line-clamp-2 text-xs leading-5 text-pretty text-slate-400">
                  {session.summary || "Runner detected; no public activity summary was provided."}
                </p>
              </button>
            ))
          ) : (
            <p className="rounded-lg border border-blue-300/10 bg-blue-300/3 p-3 text-xs leading-5 text-pretty text-slate-400">
              No supported CLI runner is active. Git file changes remain on the radar.
            </p>
          )}
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          {Object.entries(data.live.providers).map(([provider, state]) => (
            <span
              key={provider}
              title={state.error ?? undefined}
              className={cn(
                "rounded-full border px-2 py-1 font-mono text-[9px] font-semibold uppercase tracking-wider",
                state.available && !state.error
                  ? "border-emerald-400/15 bg-emerald-400/8 text-emerald-300"
                  : state.error
                    ? "border-rose-400/15 bg-rose-400/8 text-rose-300"
                    : "border-slate-700 bg-slate-800/40 text-slate-500",
              )}
            >
              {provider} {state.available ? (state.error ? "error" : "ready") : "offline"}
            </span>
          ))}
        </div>
      </section>

      <section className="web-panel p-4">
        <p className="web-label text-rose-400">Human steering</p>
        <h2 className="mt-1 font-bold text-white text-balance">Mission dispatch</h2>
        <form className="mt-3 space-y-3" onSubmit={assignWork}>
          <label className="block text-xs font-semibold text-slate-300">
            Teammate
            <input
              value={teammate}
              onChange={(event) => setTeammate(event.target.value)}
              className="web-input mt-1 px-3 text-sm"
              placeholder="Alice"
            />
          </label>
          <label className="block text-xs font-semibold text-slate-300">
            Files in scope
            <input
              value={files}
              onChange={(event) => setFiles(event.target.value)}
              className="web-input mt-1 px-3 text-sm"
              placeholder="src/app.ts, src/api.ts"
            />
          </label>
          <div className="grid grid-cols-[1fr_auto] gap-2">
            <label className="block text-xs font-semibold text-slate-300">
              Status
              <select
                value={status}
                onChange={(event) => setStatus(event.target.value as ActivityStatus)}
                className="web-input mt-1 px-3 text-sm"
              >
                <option value="pending">Queued</option>
                <option value="working">On mission</option>
                <option value="done">Secured</option>
              </select>
            </label>
            <button
              type="submit"
              disabled={pending}
              className="mt-5 min-h-10 rounded-md bg-[#d62950] px-4 font-mono text-[10px] font-bold uppercase tracking-wider text-white outline-none hover:bg-[#ef365f] focus-visible:ring-2 focus-visible:ring-rose-400 disabled:opacity-50"
            >
              Deploy
            </button>
          </div>
        </form>

        <form className="mt-4 border-t border-blue-300/10 pt-4" onSubmit={sendDirective}>
          <label className="block text-xs font-semibold text-slate-300">
            Target CLI session
            <select
              value={sessionId}
              onChange={(event) => setSessionId(event.target.value)}
              className="web-input mt-1 px-3 text-sm"
            >
              <option value="">Shared signal inbox</option>
              {data.live.sessions.map((session) => (
                <option key={`${session.provider}-${session.id}`} value={session.id}>
                  {session.name} · {session.provider} · {session.status}
                </option>
              ))}
            </select>
          </label>
          <label className="mt-3 block text-xs font-semibold text-slate-300">
            Suggest what to do next
            <textarea
              value={message}
              onChange={(event) => setMessage(event.target.value)}
              rows={3}
              maxLength={4000}
              className="web-input mt-1 resize-y px-3 py-2 text-sm"
              placeholder="Finish the API contract before changing the dashboard component."
            />
          </label>
          <button
            type="submit"
            disabled={pending}
            className="mt-2 min-h-10 w-full rounded-md border border-blue-400/45 bg-blue-500/16 px-4 font-mono text-[10px] font-bold uppercase tracking-wider text-blue-100 outline-none hover:bg-blue-500/25 focus-visible:ring-2 focus-visible:ring-blue-400 disabled:opacity-50"
          >
            {selectedSession?.provider === "codex" ? "Send signal to Codex" : "Queue web signal"}
          </button>
        </form>
        {notice ? (
          <p className="mt-3 text-xs text-pretty text-slate-400" role="status">
            {notice}
          </p>
        ) : null}
      </section>

      <section className="web-panel p-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="web-label">Source control</p>
            <h2 className="mt-1 font-bold text-white text-balance">Timeline pulse</h2>
          </div>
          <code className="rounded border border-blue-300/10 bg-blue-300/5 px-2 py-1 text-[10px] text-blue-200">
            {data.live.git.branch}
          </code>
        </div>
        <p className="mt-2 text-xs text-slate-500 tabular-nums">
          {data.live.git.dirty_files.length} live node changes · head {data.live.git.head?.slice(0, 7) ?? "unborn"}
        </p>
        {data.live.git.commits.slice(0, 3).map((commit) => (
          <div key={commit.sha} className="mt-3 border-t border-blue-300/10 pt-3">
            <p className="line-clamp-1 text-xs font-semibold text-slate-200">{commit.subject}</p>
            <p className="mt-1 font-mono text-[9px] uppercase tracking-wide text-slate-500">
              {commit.short_sha} · {commit.author} · {commit.files.length} nodes
            </p>
          </div>
        ))}
        {recentDirectives.length ? (
          <div className="mt-4 border-t border-blue-300/10 pt-3">
            <p className="web-label text-slate-500">Signal trail</p>
            {recentDirectives.map((directive) => (
              <div key={directive.id} className="mt-2 rounded-lg border border-blue-300/10 bg-blue-300/3 p-2.5">
                <div className="flex justify-between gap-2 font-mono text-[9px] font-semibold uppercase tracking-wider text-slate-500">
                  <span>{directive.teammate}</span><span>{directive.status}</span>
                </div>
                <p className="mt-1 line-clamp-2 text-xs text-pretty text-slate-300">{directive.message}</p>
                <p className="mt-1 text-[10px] text-slate-600 tabular-nums">{formatTimestamp(directive.created_at)}</p>
              </div>
            ))}
          </div>
        ) : null}
      </section>
    </aside>
  );
}
