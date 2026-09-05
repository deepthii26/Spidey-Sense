import { fireEvent, render, screen } from "@testing-library/react";
import { vi } from "vitest";

import { DashboardView } from "./DashboardView";
import { dashboardFixture } from "./test/fixtures";

describe("DashboardView", () => {
  it("renders teammate pathways, graph stats, and blocker state", async () => {
    render(
      <DashboardView
        data={dashboardFixture}
        refreshing={false}
        onRefresh={() => undefined}
        mutationPending={false}
        onUpdateActivity={async () => undefined}
        onCreateDirective={async () => undefined}
      />,
    );

    expect(screen.getByRole("heading", { name: "Team pathways" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Alice" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Bob" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Carol" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "1 blocker. Show blocker details." })).toBeInTheDocument();
    expect(screen.getByText("Bob is blocked")).toBeInTheDocument();
    expect(screen.getByText("2 files · 1 dependency")).toBeInTheDocument();
    expect(
      await screen.findByRole("heading", { name: "Live repository world" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Live CLI sessions" })).toBeInTheDocument();
    expect(await screen.findByText("3D view unavailable")).toBeInTheDocument();
  });

  it("calls the refresh action", () => {
    const refresh = vi.fn();
    render(
      <DashboardView
        data={dashboardFixture}
        refreshing={false}
        onRefresh={refresh}
        mutationPending={false}
        onUpdateActivity={async () => undefined}
        onCreateDirective={async () => undefined}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Refresh" }));

    expect(refresh).toHaveBeenCalledOnce();
  });
});
