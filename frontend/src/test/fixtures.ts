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
  live: {
    schema_version: "1.0",
    observed_at: "2026-09-05T12:00:00Z",
    git: {
      branch: "main",
      head: "8bb4323dd842a113512f128467b46dc5ee00c75e",
      remote: "git@github.com:Preethesh16/Spidey-Sense.git",
      dirty_files: [{ path: "src/app.ts", status: "M" }],
      commits: [
        {
          sha: "8bb4323dd842a113512f128467b46dc5ee00c75e",
          short_sha: "8bb4323",
          author: "Preethesh16",
          committed_at: "2026-09-05T11:30:00Z",
          subject: "Launch Spidey Sense coordination dashboard",
          files: ["src/app.ts", "src/core.ts"],
        },
      ],
    },
    sessions: [
      {
        id: "thread-1",
        provider: "codex",
        name: "Codex",
        status: "recent",
        summary: "Build a live 3D dependency view",
        updated_at: "2026-09-05T12:00:00Z",
        cwd: "/work/spidey-sense",
        files: [],
        model: "openai",
        can_message: true,
      },
    ],
    providers: {
      codex: { available: true, error: null, sessions: 1 },
      claude: { available: true, error: null, sessions: 0 },
      entire: { available: false, error: null },
    },
  },
  directives: { schema_version: "1.0", directives: [] },
};
