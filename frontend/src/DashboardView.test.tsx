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

    expect(screen.getByRole("heading", { name: "Mission pathways" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Alice" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Bob" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Carol" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "1 blocker. Show blocker details." })).toBeInTheDocument();
    expect(screen.getByText("Bob is blocked")).toBeInTheDocument();
    expect(screen.getByText("2 nodes · 1 strand")).toBeInTheDocument();
    expect(
      await screen.findByRole("heading", { name: "The Dependency Web" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Web runners" })).toBeInTheDocument();
    expect(await screen.findByText("3D web unavailable")).toBeInTheDocument();
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

    fireEvent.click(screen.getByRole("button", { name: "Scan now" }));

    expect(refresh).toHaveBeenCalledOnce();
  });
});
