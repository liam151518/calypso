import { describe, expect, it, beforeEach, vi } from "vitest";
import { render } from "@testing-library/react";

// react-konva relies on a real canvas; jsdom doesn't have one. Mock the heavy
// surface so the EditorCanvas still renders the surrounding layout, layers,
// and transformers as no-ops. Wire onClick/onTap into DOM events so we can
// exercise the selection path in jsdom.
vi.mock("react-konva", () => ({
  Stage: ({
    children,
    onClick,
  }: {
    children?: React.ReactNode;
    onClick?: (e: { target: unknown }) => void;
  }) => {
    // Provide a synthetic stage that pretends it WAS clicked on empty space.
    // The EditorCanvas stage onClick guard compares e.target === e.target.getStage();
    // we make them equal by returning the same object reference from getStage().
    const stage = {
      attrs: {},
      _isKonvaStage: true,
      getStage: () => stage,
    };
    const handleClick = () => {
      onClick?.({ target: stage });
    };
    return (
      <div data-testid="konva-stage" onClick={handleClick}>
        {children}
      </div>
    );
  },
  Layer: ({ children }: { children?: React.ReactNode }) => (
    <div data-testid="konva-layer">{children}</div>
  ),
  Rect: () => <div />,
  Text: () => <div />,
  Group: ({
    children,
    id,
    onClick,
    onTap,
  }: {
    children?: React.ReactNode;
    id?: string;
    onClick?: (e: unknown) => void;
    onTap?: () => void;
  }) => (
    <div
      data-testid={id ?? "konva-group"}
      onClick={(e) => {
        // Real Konva clicks don't bubble; we mimic that with stopPropagation
        // so the outer wrapper's "click on empty stage" guard doesn't fire.
        e.stopPropagation();
        onClick?.(e);
      }}
      onTouchEnd={(e) => {
        e.stopPropagation();
        onTap?.();
      }}
    >
      {children}
    </div>
  ),
  Transformer: () => <div />,
}));

import { buildQueryMock } from "@/test/mocks";

vi.mock("@/lib/query", () => buildQueryMock());

import { EditorCanvas } from "./Canvas";
import { useEditorStore } from "@/hooks/useEditor";
import type { TemplateLayer } from "@/lib/types";

const layers: TemplateLayer[] = [
  {
    id: "title",
    type: "text",
    name: "Title",
    x: 10,
    y: 20,
    width: 80,
    height: 12,
    config: { content: "Hi", color: "#000" },
  },
  {
    id: "product",
    type: "product_cutout",
    name: "Product",
    x: 25,
    y: 50,
    width: 50,
    height: 35,
    config: { slot: "center", shadow: true },
  },
];

describe("EditorCanvas", () => {
  beforeEach(() => {
    useEditorStore.setState((s) => {
      s.layers = [];
      s.selection = null;
    });
  });

  it("renders one Group per layer in the canvas", () => {
    useEditorStore.setState((s) => {
      s.layers = layers;
    });
    const { container } = render(<EditorCanvas showSafeZones={false} />);
    const groups = container.querySelectorAll('[data-testid^="layer-"]');
    expect(groups.length).toBe(2);
    expect(groups[0].getAttribute("data-testid")).toBe("layer-title");
    expect(groups[1].getAttribute("data-testid")).toBe("layer-product");
  });

  it("clicking a layer calls selectLayer", () => {
    useEditorStore.setState((s) => {
      s.layers = layers;
    });
    render(<EditorCanvas showSafeZones={false} />);
    // Simulate user click on the title layer group
    const titleGroup = document.querySelector('[data-testid="layer-title"]');
    titleGroup?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    expect(useEditorStore.getState().selection).toEqual({
      kind: "layer",
      id: "title",
    });
  });

  it("clicking the stage moves the selection to the canvas", () => {
    useEditorStore.setState((s) => {
      s.layers = layers;
      s.selection = { kind: "layer", id: "title" };
    });
    render(<EditorCanvas showSafeZones={false} />);
    const stage = document.querySelector('[data-testid="konva-stage"]');
    stage?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    // Clicking the empty stage moves the selection from a layer to the canvas
    // itself; downstream property panels treat this as "no layer".
    expect(useEditorStore.getState().selection).toEqual({ kind: "canvas" });
  });
});