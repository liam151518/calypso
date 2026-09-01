import { describe, expect, it, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { CaptionPanel } from "./CaptionPanel";
import { useEditorStore } from "@/hooks/useEditor";
import type { Template, Product, Brand } from "@/lib/types";

const mockGenerate = vi.fn();
const mockSelect = vi.fn();

vi.mock("@/hooks/contentFlow", () => ({
  useGenerateCaptions: () => ({
    mutate: (input: unknown, opts?: { onSuccess?: (r: { variants: unknown[] }) => void }) => {
      mockGenerate(input);
      opts?.onSuccess?.({ variants: [
        { content: "Hello world", hashtags: ["#x"], first_comment: "", alt_text: "" },
        { content: "Second take", hashtags: ["#y"], first_comment: "", alt_text: "" },
      ] });
      return { mutate: vi.fn() };
    },
    isPending: false,
  }),
  useSelectCaption: () => ({
    mutate: (input: unknown) => mockSelect(input),
    isPending: false,
  }),
}));

describe("CaptionPanel", () => {
  beforeEach(() => {
    mockGenerate.mockClear();
    mockSelect.mockClear();
    useEditorStore.setState((s) => {
      s.template = null;
      s.product = null;
      s.brand = null;
    });
  });

  it("disables Generate when template or product is missing", () => {
    render(<CaptionPanel />);
    expect(screen.getByTestId("generate-captions")).toBeDisabled();
  });

  it("calls useGenerateCaptions with the right payload", async () => {
    const tmpl = { id: 7, name: "Minimal Launch", aspect_ratio: "1:1", canvas: { width: 100, height: 100 }, layers: [] } as unknown as Template;
    const product = { id: 1, name: "Cyan" } as unknown as Product;
    const brand = { id: 2, name: "B" } as unknown as Brand;
    useEditorStore.setState((s) => {
      s.template = tmpl;
      s.product = product;
      s.brand = brand;
    });
    render(<CaptionPanel />);
    await userEvent.click(screen.getByTestId("generate-captions"));
    expect(mockGenerate).toHaveBeenCalledOnce();
    const call = mockGenerate.mock.calls[0][0];
    expect(call).toMatchObject({
      product_id: 1,
      template_id: 7,
      brand_id: 2,
      platform: "instagram",
      model: "heuristic",
    });
  });

  it("renders the returned variants", async () => {
    useEditorStore.setState((s) => {
      s.template = { id: 1, name: "t", aspect_ratio: "1:1", canvas: { width: 10, height: 10 }, layers: [] } as unknown as Template;
      s.product = { id: 1, name: "p" } as unknown as Product;
    });
    render(<CaptionPanel />);
    await userEvent.click(screen.getByTestId("generate-captions"));
    await waitFor(() => {
      expect(screen.getAllByTestId("caption-variant").length).toBe(2);
    });
  });
});