"""GitHub merge activity integration for Spidey Sense."""

from .client import (
    GITHUB_API_VERSION,
    CommitActivity,
    GitHubAPIError,
    GitHubClient,
    MergedPullRequest,
)
from .sync import GitHubSyncError, load_identity_map, sync_github_activity

__all__ = [
    "GITHUB_API_VERSION",
    "CommitActivity",
    "GitHubAPIError",
    "GitHubClient",
    "GitHubSyncError",
    "MergedPullRequest",
    "load_identity_map",
    "sync_github_activity",
]
