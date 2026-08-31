import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, act } from "@testing-library/react";
import { useState } from "react";
import { buildQueryMock } from "@/test/mocks";

vi.mock("@/lib/query", () => buildQueryMock());

import { ReferenceChipPicker } from "./ReferenceChipPicker";

function ControlledPicker({ initial }: { initial: string[] }) {
  const [selected, setSelected] = useState<string[]>(initial);
  return (
    <div>
      <ReferenceChipPicker selected={selected} onChange={setSelected} />
      <output data-testid="selected-count">{selected.length}</output>
    </div>
  );
}

describe("ReferenceChipPicker", () => {
  it("renders the open picker button and count badge", () => {
    render(<ControlledPicker initial={["ref_01.png"]} />);
    expect(screen.getByTestId("open-ref-picker")).toBeInTheDocument();
    expect(screen.getByTestId("selected-count").textContent).toBe("1");
  });

  it("opens the popover and lists references from the query hook", () => {
    render(<ControlledPicker initial={[]} />);
    act(() => {
      fireEvent.click(screen.getByTestId("open-ref-picker"));
    });
    expect(screen.getByTestId("ref-tile-ref_01.png")).toBeInTheDocument();
    expect(screen.getByTestId("ref-tile-ref_02.png")).toBeInTheDocument();
  });
});
