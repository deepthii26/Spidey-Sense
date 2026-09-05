"""Local dashboard API and static frontend server."""

from .server import DashboardService, DashboardServerError, create_server

__all__ = ["DashboardService", "DashboardServerError", "create_server"]
