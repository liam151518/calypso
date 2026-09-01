import { describe, expect, it, beforeEach, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { FeedPreview } from "./FeedPreview";

const mockUseFeed = vi.fn();
const mockUseShuffleFeed = vi.fn();

vi.mock("@/hooks/contentFlow", () => ({
  useFeed: (...args: unknown[]) => mockUseFeed(...args),
  useShuffleFeed: () => ({
    mutate: () => mockUseShuffleFeed(),
    isPending: false,
  }),
}));

describe("FeedPreview", () => {
  beforeEach(() => {
    mockUseFeed.mockReset();
    mockUseShuffleFeed.mockClear();
  });

  it("renders the 3x3 grid when the API returns items", () => {
    mockUseFeed.mockReturnValue({
      data: { items: Array.from({ length: 9 }, (_, i) => ({
        id: i + 1,
        rel_url: `outputs/images/${i + 1}.jpg`,
        filename: `${i + 1}.jpg`,
      })) },
      isLoading: false,
    });
    render(<FeedPreview />);
    expect(screen.getAllByRole("img").length).toBe(9);
  });

  it("shows an empty state when there are no items", () => {
    mockUseFeed.mockReturnValue({ data: { items: [] }, isLoading: false });
    render(<FeedPreview />);
    expect(screen.getByText(/no outputs yet/i)).toBeInTheDocument();
  });

  it("triggers shuffle when the button is clicked", async () => {
    mockUseFeed.mockReturnValue({
      data: { items: [{ id: 1, rel_url: "x.jpg", filename: "x.jpg" }] },
      isLoading: false,
    });
    render(<FeedPreview />);
    await userEvent.click(screen.getByRole("button", { name: /shuffle/i }));
    expect(mockUseShuffleFeed).toHaveBeenCalledOnce();
  });

  it("highlights the new output when newOutputId is set", () => {
    mockUseFeed.mockReturnValue({
      data: { items: [
        { id: 7, rel_url: "a.jpg", filename: "a.jpg" },
        { id: 8, rel_url: "b.jpg", filename: "b.jpg" },
      ] },
      isLoading: false,
    });
    const { container } = render(<FeedPreview newOutputId={7} />);
    const tiles = container.querySelectorAll('[data-testid="feed-item"]');
    expect(tiles[0].className).toMatch(/ring-2/);
    expect(tiles[1].className).not.toMatch(/ring-2/);
  });
});