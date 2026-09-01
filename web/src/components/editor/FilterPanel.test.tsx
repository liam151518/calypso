import { describe, expect, it, beforeEach, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { MOCK_FILTERS } from "@/test/mocks";

// The hooks/templates module exports `useFilters`; mock it directly so we
// don't have to spin up a QueryClientProvider for these tests.
vi.mock("@/hooks/templates", () => ({
  useFilters: () => ({ data: { presets: MOCK_FILTERS, user: [] }, isLoading: false }),
}));

import { FilterPanel } from "./FilterPanel";
import { useEditorStore } from "@/hooks/useEditor";

describe("FilterPanel", () => {
  beforeEach(() => {
    useEditorStore.setState((s) => {
      s.filter = null;
      s.filterIntensity = 1;
    });
  });

  it("renders a button for every preset returned by useFilters", () => {
    render(<FilterPanel />);
    for (const preset of MOCK_FILTERS) {
      expect(
        screen.getByRole("button", { name: preset.name }),
      ).toBeInTheDocument();
    }
  });

  it("clicking a preset calls setFilter", async () => {
    render(<FilterPanel />);
    await userEvent.click(screen.getByRole("button", { name: "moody" }));
    expect(useEditorStore.getState().filter).toBe("moody");
  });

  it("the intensity slider scales the value in the store", () => {
    render(<FilterPanel />);
    const slider = screen.getByLabelText("Filter intensity") as HTMLInputElement;
    // The slider is a controlled <input type="range">; React tracks the value
    // through the synthetic event system, so we use the native setter to
    // dispatch a real input change that React picks up.
    const setter = Object.getOwnPropertyDescriptor(
      HTMLInputElement.prototype,
      "value",
    )?.set;
    setter?.call(slider, "0.5");
    slider.dispatchEvent(new Event("input", { bubbles: true }));
    expect(useEditorStore.getState().filterIntensity).toBeCloseTo(0.5, 1);
  });
});