import { useCallback, useEffect, useState } from "react";

import { DashboardView } from "./DashboardView";
import type { ActivityUpdate, DashboardPayload, DirectiveInput } from "./types";

function LoadingDashboard() {
  return (
    <div className="spidey-shell min-h-dvh bg-[#030711]" role="status" aria-label="Loading dashboard">
      <div className="border-b border-blue-400/10 bg-[#050b18]/90 px-6 py-5">
        <div className="mx-auto h-10 max-w-[94rem] animate-pulse rounded-lg bg-blue-400/10" />
      </div>
      <div className="mx-auto max-w-[94rem] space-y-6 px-6 py-8">
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          {[0, 1, 2, 3].map((item) => (
            <div key={item} className="h-24 rounded-xl border border-blue-400/10 bg-blue-400/5" />
          ))}
        </div>
        <div className="h-[32rem] rounded-2xl border border-blue-400/10 bg-blue-400/5" />
      </div>
      <span className="sr-only">Loading Spidey Sense data…</span>
    </div>
  );
}

export default function App() {
  const [data, setData] = useState<DashboardPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [mutationPending, setMutationPending] = useState(false);
  const [mutationError, setMutationError] = useState<string | null>(null);

  const loadDashboard = useCallback(async (silent = false) => {
    if (!silent) {
      setRefreshing(true);
      setError(null);
    }
    try {
      const response = await fetch("/api/dashboard", {
        headers: { Accept: "application/json" },
      });
      if (!response.ok) {
        const details = (await response.json().catch(() => null)) as { error?: string } | null;
        throw new Error(details?.error ?? `Dashboard request failed with HTTP ${response.status}`);
      }
      setData((await response.json()) as DashboardPayload);
    } catch (caught) {
      if (!silent) {
        setError(caught instanceof Error ? caught.message : "Could not load dashboard data");
      }
    } finally {
      if (!silent) setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void loadDashboard();
    const interval = window.setInterval(() => {
      if (document.visibilityState === "visible") void loadDashboard(true);
    }, 3000);
    return () => window.clearInterval(interval);
  }, [loadDashboard]);

  const postJSON = useCallback(
    async (path: string, value: ActivityUpdate | DirectiveInput) => {
      setMutationPending(true);
      setMutationError(null);
      try {
        const response = await fetch(path, {
          method: "POST",
          headers: { Accept: "application/json", "Content-Type": "application/json" },
          body: JSON.stringify(value),
        });
        if (!response.ok) {
          const details = (await response.json().catch(() => null)) as { error?: string } | null;
          throw new Error(details?.error ?? `Request failed with HTTP ${response.status}`);
        }
        await loadDashboard(true);
      } catch (caught) {
        const message = caught instanceof Error ? caught.message : "Could not update mission control";
        setMutationError(message);
        throw caught;
      } finally {
        setMutationPending(false);
      }
    },
    [loadDashboard],
  );

  if (!data && refreshing) return <LoadingDashboard />;

  if (!data) {
    return (
      <main className="spidey-shell grid min-h-dvh place-items-center bg-[#030711] p-6 text-slate-100">
        <div className="web-panel w-full max-w-md p-6">
          <p className="web-label text-rose-400">Signal lost</p>
          <h1 className="mt-2 text-xl font-bold text-balance">The local data API is unavailable</h1>
          <p className="mt-2 text-sm text-pretty text-slate-400">{error}</p>
          <button
            type="button"
            onClick={() => void loadDashboard()}
            className="mt-5 min-h-10 rounded-lg bg-[#d62950] px-4 py-2 text-sm font-semibold text-white outline-none hover:bg-[#ee365f] focus-visible:ring-2 focus-visible:ring-rose-400"
          >
            Try again
          </button>
        </div>
      </main>
    );
  }

  return (
    <>
      {error ? (
        <div role="alert" className="border-b border-red-500/30 bg-red-950 px-4 py-2 text-center text-sm text-red-100">
          Refresh failed: {error}
        </div>
      ) : null}
      {mutationError ? (
        <div role="alert" className="border-b border-red-500/30 bg-red-950 px-4 py-2 text-center text-sm text-red-100">
          Mission update failed: {mutationError}
        </div>
      ) : null}
      <DashboardView
        data={data}
        refreshing={refreshing}
        onRefresh={() => void loadDashboard()}
        mutationPending={mutationPending}
        onUpdateActivity={(value) => postJSON("/api/activity", value)}
        onCreateDirective={(value) => postJSON("/api/directives", value)}
      />
    </>
  );
}
