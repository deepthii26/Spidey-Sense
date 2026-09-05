import { render, screen } from "@testing-library/react";
import { afterEach, vi } from "vitest";

import App from "./App";
import { dashboardFixture } from "./test/fixtures";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("App", () => {
  it("loads dashboard data from the local API", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => dashboardFixture,
      }),
    );

    render(<App />);

    expect(await screen.findByRole("heading", { name: "Spidey Sense" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Alice" })).toBeInTheDocument();
  });

  it("shows a retry action beside API errors", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("Connection refused")));

    render(<App />);

    expect(await screen.findByText("Couldn’t load dashboard")).toBeInTheDocument();
    expect(screen.getByText("Connection refused")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });
});
