import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SuggestionCard } from "./SuggestionCard";

const sample = {
  template_id: 7,
  layer_overrides: {},
  rationale: "A bold tone pairs well with the streetwear vibe.",
  platforms: ["instagram", "tiktok"],
  duration_s: 30,
  cost_usd: 0.85,
  confidence_score: 0.75,
};

describe("SuggestionCard", () => {
  it("renders preview, rationale, confidence, and cost", () => {
    render(
      <SuggestionCard
        suggestion={sample}
        previewUrl="data:image/png;base64,AA"
        onAccept={vi.fn()}
        onSchedule={vi.fn()}
        onReject={vi.fn()}
      />
    );
    expect(screen.getByText(/75%/)).toBeInTheDocument();
    expect(screen.getByText(/0\.85/)).toBeInTheDocument();
    expect(
      screen.getByText(/A bold tone pairs well/)
    ).toBeInTheDocument();
  });

  it("invokes onAccept when Edit is clicked", async () => {
    const onAccept = vi.fn();
    render(
      <SuggestionCard
        suggestion={sample}
        onAccept={onAccept}
        onSchedule={vi.fn()}
        onReject={vi.fn()}
      />
    );
    await userEvent.click(screen.getByRole("button", { name: /edit/i }));
    expect(onAccept).toHaveBeenCalledWith(sample);
  });

  it("invokes onSchedule when Schedule is clicked", async () => {
    const onSchedule = vi.fn();
    render(
      <SuggestionCard
        suggestion={sample}
        onAccept={vi.fn()}
        onSchedule={onSchedule}
        onReject={vi.fn()}
      />
    );
    await userEvent.click(screen.getByRole("button", { name: /schedule/i }));
    expect(onSchedule).toHaveBeenCalledWith(sample);
  });

  it("disables Edit and Schedule when no template_id", () => {
    render(
      <SuggestionCard
        suggestion={{ ...sample, template_id: null }}
        onAccept={vi.fn()}
        onSchedule={vi.fn()}
        onReject={vi.fn()}
      />
    );
    expect(screen.getByRole("button", { name: /edit/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /schedule/i })).toBeDisabled();
  });
});