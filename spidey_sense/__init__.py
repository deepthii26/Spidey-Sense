"""Spidey Sense dependency graph engine."""

from .activity import ActivityRecord, ActivityStore, ActivityStoreError
from .blockers import BlockerDataError, detect_blockers, load_dependency_graph
from .dashboard import DashboardService, DashboardServerError
from .github import GitHubAPIError, GitHubClient, sync_github_activity
from .graph import DependencyGraphBuilder, GraphBuildError, build_dependency_graph
from .live import DirectiveStore, LiveTelemetryCollector

__all__ = [
    "ActivityRecord",
    "ActivityStore",
    "ActivityStoreError",
    "BlockerDataError",
    "DependencyGraphBuilder",
    "DashboardService",
    "DashboardServerError",
    "GraphBuildError",
    "GitHubAPIError",
    "GitHubClient",
    "DirectiveStore",
    "LiveTelemetryCollector",
    "build_dependency_graph",
    "detect_blockers",
    "load_dependency_graph",
    "sync_github_activity",
]
__version__ = "0.6.0"
