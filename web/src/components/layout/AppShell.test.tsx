import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { buildQueryMock } from "@/test/mocks";

vi.mock("@/lib/query", () => buildQueryMock());

import { AppShell } from "./AppShell";

describe("AppShell", () => {
  it("renders the nav links and brand mark", () => {
    render(
      <MemoryRouter initialEntries={["/generate"]}>
        <AppShell />
      </MemoryRouter>,
    );
    expect(screen.getByTestId("nav-generate")).toBeInTheDocument();
    expect(screen.getByTestId("nav-image")).toBeInTheDocument();
    expect(screen.getByTestId("nav-outputs")).toBeInTheDocument();
    expect(screen.getByTestId("nav-references")).toBeInTheDocument();
    expect(screen.getByTestId("nav-brand")).toBeInTheDocument();
    expect(screen.getByTestId("nav-settings")).toBeInTheDocument();
  });
});
