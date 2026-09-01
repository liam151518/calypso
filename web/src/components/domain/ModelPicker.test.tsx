import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { buildQueryMock } from "@/test/mocks";

vi.mock("@/lib/query", () => buildQueryMock());

import { ModelPicker } from "./ModelPicker";
import { MOCK_MODELS } from "@/test/mocks";

describe("ModelPicker", () => {
  it("renders the trigger with the selected model name", () => {
    render(
      <ModelPicker
        models={MOCK_MODELS}
        category="video"
        value="minimax/h3"
        onChange={() => {}}
        duration={8}
        resolution="768p"
      />,
    );
    expect(screen.getByText("MiniMax H3")).toBeInTheDocument();
  });

  it("shows the live cost estimate badge for video", () => {
    render(
      <ModelPicker
        models={MOCK_MODELS}
        category="video"
        value="minimax/h3"
        onChange={() => {}}
        duration={8}
        resolution="768p"
      />,
    );
    const badge = screen.getByTestId("model-cost-video");
    expect(badge).toBeInTheDocument();
    // 0.045 * 8 = 0.36 → formatted with 2dp (since >= 0.1).
    expect(badge.textContent).toMatch(/\$0\.36/);
  });

  it("shows the live cost estimate badge for image", () => {
    render(
      <ModelPicker
        models={MOCK_MODELS}
        category="image"
        value="flux-pro/v1.1"
        onChange={() => {}}
        aspect_ratio="1:1"
        num_images={2}
      />,
    );
    const badge = screen.getByTestId("model-cost-image");
    expect(badge).toBeInTheDocument();
    // 0.05 * 2 = 0.10 → formatted with 2dp.
    expect(badge.textContent).toMatch(/\$0\.10/);
  });

  it("renders fallback text when no model is selected", () => {
    render(
      <ModelPicker
        models={MOCK_MODELS}
        category="video"
        value=""
        onChange={() => {}}
        duration={8}
        resolution="768p"
      />,
    );
    expect(screen.getAllByText(/Pick a model/i).length).toBeGreaterThan(0);
    expect(screen.getByTestId("model-cost-video").textContent).toMatch(/—/);
  });
});
