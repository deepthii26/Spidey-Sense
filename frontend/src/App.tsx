import { useCallback, useEffect, useState } from "react";

import { DashboardView } from "./DashboardView";
import type { DashboardPayload } from "./types";

function LoadingDashboard() {
  return (
    <div className="min-h-dvh bg-slate-50" role="status" aria-label="Loading dashboard">
      <div className="border-b border-slate-200 bg-white px-6 py-5">
        <div className="mx-auto h-10 max-w-7xl rounded-lg bg-slate-200" />
      </div>
      <div className="mx-auto max-w-7xl space-y-6 px-6 py-8">
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          {[0, 1, 2, 3].map((item) => (
            <div key={item} className="h-24 rounded-xl border border-slate-200 bg-white" />
          ))}
        </div>
        <div className="h-64 rounded-2xl border border-slate-200 bg-white" />
      </div>
      <span className="sr-only">Loading Spidey Sense data…</span>
    </div>
  );
}

export default function App() {
  const [data, setData] = useState<DashboardPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const loadDashboard = useCallback(async () => {
    setRefreshing(true);
    setError(null);
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
      setError(caught instanceof Error ? caught.message : "Could not load dashboard data");
    } finally {
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void loadDashboard();
  }, [loadDashboard]);

  if (!data && refreshing) return <LoadingDashboard />;

  if (!data) {
    return (
      <main className="grid min-h-dvh place-items-center bg-slate-50 p-6">
        <div className="w-full max-w-md rounded-2xl border border-red-200 bg-white p-6 shadow-sm">
          <p className="text-sm font-semibold text-red-700">Couldn’t load dashboard</p>
          <h1 className="mt-2 text-xl font-bold text-balance">The local data API is unavailable</h1>
          <p className="mt-2 text-sm text-pretty text-slate-600">{error}</p>
          <button
            type="button"
            onClick={() => void loadDashboard()}
            className="mt-5 min-h-10 rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white outline-none hover:bg-blue-700 focus-visible:ring-2 focus-visible:ring-blue-600 focus-visible:ring-offset-2"
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
        <div role="alert" className="border-b border-red-200 bg-red-50 px-4 py-2 text-center text-sm text-red-800">
          Refresh failed: {error}
        </div>
      ) : null}
      <DashboardView data={data} refreshing={refreshing} onRefresh={() => void loadDashboard()} />
    </>
  );
}
