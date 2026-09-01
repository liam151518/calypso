import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import { buildQueryMock } from "@/test/mocks";

vi.mock("@/lib/query", () => buildQueryMock());

import { ImageComposer } from "./ImageComposer";

describe("ImageComposer", () => {
  it("submits with the expected payload", () => {
    const onSubmit = vi.fn();
    render(
      <ImageComposer
        refId={null}
        onChangeRefId={() => {}}
        onSubmit={onSubmit}
      />,
    );
    const prompt = screen.getByTestId("image-prompt-input");
    fireEvent.change(prompt, { target: { value: "A samurai helmet" } });
    fireEvent.click(screen.getByTestId("submit-image"));
    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        prompt: "A samurai helmet",
        model: "flux-pro/v1.1",
        aspect_ratio: "1:1",
        num_images: 1,
        ref_id: null,
        brand_id: null,
      }),
    );
  });

  it("disables submit when prompt is empty", () => {
    render(
      <ImageComposer
        refId={null}
        onChangeRefId={() => {}}
        onSubmit={() => {}}
      />,
    );
    expect(screen.getByTestId("submit-image")).toBeDisabled();
  });

  it("shows the active reference id", () => {
    render(
      <ImageComposer
        refId="ref_01.png"
        onChangeRefId={() => {}}
        onSubmit={() => {}}
      />,
    );
    expect(screen.getByText(/ref_01\.png/)).toBeInTheDocument();
  });
});
