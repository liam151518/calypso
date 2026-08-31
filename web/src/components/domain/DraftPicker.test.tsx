import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { buildQueryMock } from "@/test/mocks";

vi.mock("@/lib/query", () => buildQueryMock());

import { DraftPicker } from "./DraftPicker";

describe("DraftPicker", () => {
  it("opens the dialog, filters drafts, and picks one", async () => {
    const onPick = vi.fn();
    render(<DraftPicker onPick={onPick} />);
    fireEvent.click(screen.getByTestId("open-draft-picker"));

    await waitFor(() => {
      expect(screen.getByTestId("draft-item-1")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("draft-item-1"));
    expect(onPick).toHaveBeenCalledWith({
      id: 1,
      name: "Damascus reveal",
      body: "Damascus cabinet reveal, golden hour, slow dolly.",
    });
  });
});
