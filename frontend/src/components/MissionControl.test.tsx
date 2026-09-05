import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";

import { dashboardFixture } from "../test/fixtures";
import { MissionControl } from "./MissionControl";

describe("MissionControl", () => {
  it("publishes a changed teammate mission", async () => {
    const update = vi.fn().mockResolvedValue(undefined);
    render(
      <MissionControl
        data={dashboardFixture}
        pending={false}
        onUpdateActivity={update}
        onCreateDirective={async () => undefined}
      />,
    );

    fireEvent.change(screen.getByLabelText("Teammate"), { target: { value: "Dana" } });
    fireEvent.change(screen.getByLabelText("Files in scope"), {
      target: { value: "src/api.ts, src/db.ts" },
    });
    fireEvent.change(screen.getByLabelText("Status"), { target: { value: "working" } });
    fireEvent.click(screen.getByRole("button", { name: "Deploy" }));

    await waitFor(() =>
      expect(update).toHaveBeenCalledWith({
        teammate: "Dana",
        files: ["src/api.ts", "src/db.ts"],
        status: "working",
      }),
    );
  });

  it("can send a directive directly to a discovered Codex thread", async () => {
    const createDirective = vi.fn().mockResolvedValue(undefined);
    render(
      <MissionControl
        data={dashboardFixture}
        pending={false}
        onUpdateActivity={async () => undefined}
        onCreateDirective={createDirective}
      />,
    );

    fireEvent.change(screen.getByLabelText("Target CLI session"), {
      target: { value: "thread-1" },
    });
    fireEvent.change(screen.getByLabelText("Suggest what to do next"), {
      target: { value: "Run the contract tests before changing the UI." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send signal to Codex" }));

    await waitFor(() =>
      expect(createDirective).toHaveBeenCalledWith({
        teammate: "Alice",
        message: "Run the contract tests before changing the UI.",
        provider: "codex",
        session_id: "thread-1",
        deliver_now: true,
      }),
    );
  });
});
