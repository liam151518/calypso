import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { buildQueryMock } from "@/test/mocks";

vi.mock("@/lib/query", () => buildQueryMock());

import { PromptComposer } from "./PromptComposer";

describe("PromptComposer", () => {
  it("submits the right shape including ref_ids and brand_id", () => {
    const onSubmit = vi.fn();
    render(
      <PromptComposer
        refIds={["ref_01.png", "ref_02.png"]}
        brandId={42}
        onSubmit={onSubmit}
      />,
    );
    fireEvent.change(screen.getByTestId("prompt-input"), {
      target: { value: "Hero draws blade" },
    });
    fireEvent.click(screen.getByTestId("submit-generate"));
    expect(onSubmit).toHaveBeenCalledWith({
      prompt: "Hero draws blade",
      // Default model id comes from the mocked /api/models defaults.
      model: "minimax/h3",
      duration: 8,
      resolution: "768p",
      ref_ids: ["ref_01.png", "ref_02.png"],
      draft_id: null,
      brand_id: 42,
    });
  });

  it("disables submit when prompt is empty", () => {
    const onSubmit = vi.fn();
    render(<PromptComposer refIds={[]} onSubmit={onSubmit} />);
    const btn = screen.getByTestId("submit-generate") as HTMLButtonElement;
    expect(btn.disabled).toBe(true);
    fireEvent.click(btn);
    expect(onSubmit).not.toHaveBeenCalled();
  });
});
