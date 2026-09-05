import type { DashboardPayload } from "../types";

export const dashboardFixture: DashboardPayload = {
  schema_version: "1.0",
  generated_at: "2026-09-05T12:00:00Z",
  repository: "/work/spidey-sense",
  graph: {
    nodes: [
      { id: "src/app.ts", path: "src/app.ts", language: "typescript" },
      { id: "src/core.ts", path: "src/core.ts", language: "typescript" },
    ],
    edges: [{ source: "src/app.ts", target: "src/core.ts", kind: "import" }],
    stats: { nodes: 2, edges: 1, diagnostics: 0 },
  },
  activity: {
    schema_version: "1.0",
    teammates: {
      alice: {
        teammate: "Alice",
        files: ["src/core.ts"],
        status: "working",
        updated_at: "2026-09-05T11:55:00Z",
      },
      bob: {
        teammate: "Bob",
        files: ["src/app.ts"],
        status: "working",
        updated_at: "2026-09-05T11:54:00Z",
      },
      carol: {
        teammate: "Carol",
        files: ["src/complete.ts"],
        status: "done",
        updated_at: "2026-09-05T11:50:00Z",
      },
    },
  },
  blockers: [
    {
      blocking_teammate: "Alice",
      blocked_teammate: "Bob",
      type: "dependency",
      blocking_file: "src/core.ts",
      blocked_file: "src/app.ts",
      reciprocal: false,
      dependency: { source: "src/app.ts", target: "src/core.ts", kind: "import" },
    },
  ],
  github_sync: null,
};
