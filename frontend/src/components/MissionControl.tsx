import { type FormEvent, useMemo, useState } from "react";

import { cn, formatTimestamp } from "../lib/utils";
import type {
  ActivityStatus,
  ActivityUpdate,
  DashboardPayload,
  DirectiveInput,
} from "../types";

const providerColors: Record<string, string> = {
  codex: "bg-emerald-400",
  claude: "bg-orange-400",
  entire: "bg-fuchsia-400",
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
    const parsedFiles = files.split(/[\n,]/).map((file) => file.trim()).filter(Boolean);
    if (!teammate.trim() || !parsedFiles.length) {
      setNotice("Add a teammate and at least one repository-relative file.");
      return;
    }
    try {
      await onUpdateActivity({ teammate: teammate.trim(), files: parsedFiles, status });
      setNotice(`Updated ${teammate.trim()}'s mission.`);
    } catch {
      setNotice("The mission update was rejected. Check the error above.");
    }
  }

  async function sendDirective(event: FormEvent) {
    event.preventDefault();
    if (!teammate.trim() || !message.trim()) {
      setNotice("Choose a teammate and write a directive first.");
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
          ? "Directive sent to the Codex thread."
          : "Directive added to the agent inbox.",
      );
    } catch {
      setNotice("The directive could not be delivered. Check the error above.");
    }
  }

  return (
    <aside className="space-y-4" aria-label="Live mission control">
      <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-[11px] font-bold uppercase text-blue-700">Agent radar</p>
            <h2 className="font-bold text-balance">Live CLI sessions</h2>
          </div>
          <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-2.5 py-1 text-[11px] font-bold text-emerald-800">
            <span className="size-2 rounded-full bg-emerald-500" />
            LIVE · 3s
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
                  "w-full rounded-xl border p-3 text-left outline-none focus-visible:ring-2 focus-visible:ring-blue-600",
                  sessionId === session.id
                    ? "border-blue-400 bg-blue-50"
                    : "border-slate-200 hover:border-slate-300",
                )}
              >
                <div className="flex items-center justify-between gap-3">
                  <span className="flex items-center gap-2 text-xs font-bold capitalize">
                    <span className={cn("size-2 rounded-full", providerColors[session.provider])} />
                    {session.name} · {session.provider}
                  </span>
                  <span className="text-[10px] font-semibold uppercase text-slate-500">{session.status}</span>
                </div>
                <p className="mt-1.5 line-clamp-2 text-xs leading-5 text-pretty text-slate-600">
                  {session.summary || "Session is visible; no public summary was provided."}
                </p>
              </button>
            ))
          ) : (
            <p className="rounded-xl bg-slate-50 p-3 text-xs leading-5 text-pretty text-slate-600">
              No supported CLI session is active. Git file changes are still monitored live.
            </p>
          )}
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          {Object.entries(data.live.providers).map(([provider, state]) => (
            <span
              key={provider}
              title={state.error ?? undefined}
              className={cn(
                "rounded-full px-2 py-1 text-[10px] font-semibold capitalize",
                state.available && !state.error
                  ? "bg-emerald-50 text-emerald-800"
                  : state.error
                    ? "bg-red-50 text-red-800"
                    : "bg-slate-100 text-slate-500",
              )}
            >
              {provider} {state.available ? (state.error ? "error" : "ready") : "not installed"}
            </span>
          ))}
        </div>
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
        <p className="text-[11px] font-bold uppercase text-violet-700">Human steering</p>
        <h2 className="font-bold text-balance">Change the mission</h2>
        <form className="mt-3 space-y-3" onSubmit={assignWork}>
          <label className="block text-xs font-semibold text-slate-700">
            Teammate
            <input
              value={teammate}
              onChange={(event) => setTeammate(event.target.value)}
              className="mt-1 min-h-10 w-full rounded-lg border border-slate-300 px-3 text-sm outline-none focus-visible:border-blue-500 focus-visible:ring-2 focus-visible:ring-blue-200"
              placeholder="Alice"
            />
          </label>
          <label className="block text-xs font-semibold text-slate-700">
            Files in scope
            <input
              value={files}
              onChange={(event) => setFiles(event.target.value)}
              className="mt-1 min-h-10 w-full rounded-lg border border-slate-300 px-3 text-sm outline-none focus-visible:border-blue-500 focus-visible:ring-2 focus-visible:ring-blue-200"
              placeholder="src/app.ts, src/api.ts"
            />
          </label>
          <div className="grid grid-cols-[1fr_auto] gap-2">
            <label className="block text-xs font-semibold text-slate-700">
              Status
              <select
                value={status}
                onChange={(event) => setStatus(event.target.value as ActivityStatus)}
                className="mt-1 min-h-10 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm outline-none focus-visible:border-blue-500 focus-visible:ring-2 focus-visible:ring-blue-200"
              >
                <option value="pending">Pending</option>
                <option value="working">Working</option>
                <option value="done">Done</option>
              </select>
            </label>
            <button
              type="submit"
              disabled={pending}
              className="mt-5 min-h-10 rounded-lg bg-slate-950 px-4 text-xs font-bold text-white outline-none hover:bg-slate-800 focus-visible:ring-2 focus-visible:ring-slate-700 disabled:opacity-50"
            >
              Assign
            </button>
          </div>
        </form>

        <form className="mt-4 border-t border-slate-100 pt-4" onSubmit={sendDirective}>
          <label className="block text-xs font-semibold text-slate-700">
            Target CLI session
            <select
              value={sessionId}
              onChange={(event) => setSessionId(event.target.value)}
              className="mt-1 min-h-10 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm outline-none focus-visible:border-blue-500 focus-visible:ring-2 focus-visible:ring-blue-200"
            >
              <option value="">Shared directive inbox</option>
              {data.live.sessions.map((session) => (
                <option key={`${session.provider}-${session.id}`} value={session.id}>
                  {session.name} · {session.provider} · {session.status}
                </option>
              ))}
            </select>
          </label>
          <label className="mt-3 block text-xs font-semibold text-slate-700">
            Suggest what to do next
            <textarea
              value={message}
              onChange={(event) => setMessage(event.target.value)}
              rows={3}
              maxLength={4000}
              className="mt-1 w-full resize-y rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus-visible:border-blue-500 focus-visible:ring-2 focus-visible:ring-blue-200"
              placeholder="Finish the API contract before changing the dashboard component."
            />
          </label>
          <button
            type="submit"
            disabled={pending}
            className="mt-2 min-h-10 w-full rounded-lg bg-blue-600 px-4 text-xs font-bold text-white outline-none hover:bg-blue-700 focus-visible:ring-2 focus-visible:ring-blue-600 focus-visible:ring-offset-2 disabled:opacity-50"
          >
            {selectedSession?.provider === "codex" ? "Send to Codex now" : "Queue directive"}
          </button>
        </form>
        {notice ? <p className="mt-3 text-xs text-pretty text-slate-600" role="status">{notice}</p> : null}
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex items-center justify-between gap-3">
          <h2 className="font-bold text-balance">Git pulse</h2>
          <code className="rounded bg-slate-100 px-2 py-1 text-[10px] text-slate-700">{data.live.git.branch}</code>
        </div>
        <p className="mt-2 text-xs text-slate-500 tabular-nums">
          {data.live.git.dirty_files.length} live file changes · head {data.live.git.head?.slice(0, 7) ?? "unborn"}
        </p>
        {data.live.git.commits.slice(0, 3).map((commit) => (
          <div key={commit.sha} className="mt-3 border-t border-slate-100 pt-3">
            <p className="line-clamp-1 text-xs font-semibold text-slate-800">{commit.subject}</p>
            <p className="mt-1 text-[10px] text-slate-500">
              {commit.short_sha} · {commit.author} · {commit.files.length} files
            </p>
          </div>
        ))}
        {recentDirectives.length ? (
          <div className="mt-4 border-t border-slate-100 pt-3">
            <p className="text-[11px] font-bold uppercase text-slate-500">Directive trail</p>
            {recentDirectives.map((directive) => (
              <div key={directive.id} className="mt-2 rounded-lg bg-slate-50 p-2.5">
                <div className="flex justify-between gap-2 text-[10px] font-semibold uppercase text-slate-500">
                  <span>{directive.teammate}</span><span>{directive.status}</span>
                </div>
                <p className="mt-1 line-clamp-2 text-xs text-pretty text-slate-700">{directive.message}</p>
                <p className="mt-1 text-[10px] text-slate-400 tabular-nums">{formatTimestamp(directive.created_at)}</p>
              </div>
            ))}
          </div>
        ) : null}
      </section>
    </aside>
  );
}
