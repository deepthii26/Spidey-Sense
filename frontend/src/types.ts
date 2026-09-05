export type ActivityStatus = "pending" | "working" | "done";

export interface ActivityRecord {
  teammate: string;
  files: string[];
  status: ActivityStatus;
  updated_at: string;
}

export interface DependencyEdge {
  source: string;
  target: string;
  kind?: string;
  specifier?: string;
  line?: number;
}

export interface Blocker {
  blocking_teammate: string;
  blocked_teammate: string;
  type: "dependency" | "same_file";
  blocking_file: string;
  blocked_file: string;
  reciprocal: boolean;
  dependency: DependencyEdge | null;
}

export interface GitHubCommit {
  sha: string;
  message: string;
  author_login: string | null;
  committed_at: string | null;
  entire_checkpoint_ids: string[];
}

export interface MergedPullRequest {
  number: number;
  title: string;
  author_login: string;
  merged_at: string;
  merge_commit_sha: string | null;
  html_url: string;
  files: string[];
  commits: GitHubCommit[];
}

export interface GitHubSyncResult {
  repository: string;
  checked_at: string;
  merged_pull_requests: MergedPullRequest[];
  updates: Array<{
    teammate: string;
    previous_status: ActivityStatus;
    status: "done";
    matched_files: string[];
  }>;
  skipped_updates: unknown[];
}

export interface LiveSession {
  id: string;
  provider: "codex" | "claude" | "entire";
  name: string;
  status: string;
  summary: string;
  updated_at: string | null;
  cwd: string | null;
  files: string[];
  model: string | null;
  can_message: boolean;
}

export interface GitTelemetry {
  branch: string;
  head: string | null;
  remote: string | null;
  dirty_files: Array<{ path: string; status: string }>;
  commits: Array<{
    sha: string;
    short_sha: string;
    author: string;
    committed_at: string;
    subject: string;
    files: string[];
  }>;
}

export interface Directive {
  id: string;
  teammate: string;
  message: string;
  provider: "inbox" | "codex" | "claude" | "entire";
  session_id: string | null;
  status: "queued" | "sent" | "acknowledged" | "failed";
  created_at: string;
  delivered_at: string | null;
  error: string | null;
}

export interface DashboardPayload {
  schema_version: "1.0";
  generated_at: string;
  repository: string;
  graph: {
    nodes: Array<{ id: string; path: string; language: string }>;
    edges: DependencyEdge[];
    stats: { nodes: number; edges: number; diagnostics: number };
  };
  activity: {
    schema_version: "1.0";
    teammates: Record<string, ActivityRecord>;
  };
  blockers: Blocker[];
  github_sync: GitHubSyncResult | null;
  live: {
    schema_version: "1.0";
    observed_at: string;
    git: GitTelemetry;
    sessions: LiveSession[];
    providers: Record<
      string,
      { available: boolean; error: string | null; sessions?: number }
    >;
  };
  directives: {
    schema_version: "1.0";
    directives: Directive[];
  };
}

export interface ActivityUpdate {
  teammate: string;
  files: string[];
  status: ActivityStatus;
}

export interface DirectiveInput {
  teammate: string;
  message: string;
  provider: "inbox" | "codex" | "claude" | "entire";
  session_id?: string;
  deliver_now: boolean;
}
