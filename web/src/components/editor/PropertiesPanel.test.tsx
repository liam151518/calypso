import { describe, expect, it, beforeEach, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { buildQueryMock } from "@/test/mocks";

vi.mock("@/lib/query", () => buildQueryMock());

import { PropertiesPanel } from "./PropertiesPanel";
import { useEditorStore } from "@/hooks/useEditor";
import type { TemplateLayer } from "@/lib/types";

const sampleTextLayer: TemplateLayer = {
  id: "title",
  type: "text",
  name: "Title",
  x: 10,
  y: 20,
  width: 50,
  height: 12,
  config: {
    content: "Hello world",
    color: "#111111",
    font_size: 48,
    font_family: "sans-serif",
    text_align: "left",
  },
};

describe("PropertiesPanel", () => {
  beforeEach(() => {
    useEditorStore.setState((s) => {
      s.layers = [];
      s.selection = null;
      s.history = { past: [], future: [] };
      s.dirty = false;
    });
  });

  it("shows the empty-state message when no layer is selected", () => {
    render(<PropertiesPanel />);
    expect(screen.getByText(/Select a layer to edit/)).toBeInTheDocument();
  });

  it("shows position + text config for a selected text layer", () => {
    useEditorStore.setState((s) => {
      s.layers = [sampleTextLayer];
      s.selection = { kind: "layer", id: "title" };
    });
    render(<PropertiesPanel />);
    expect(screen.getByText("Properties")).toBeInTheDocument();
    expect(screen.getByText("Position")).toBeInTheDocument();
    expect(screen.getByText("Text")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Hello world")).toBeInTheDocument();
  });

  it("editing the X % position field calls updateLayerProps", async () => {
    useEditorStore.setState((s) => {
      s.layers = [sampleTextLayer];
      s.selection = { kind: "layer", id: "title" };
    });
    render(<PropertiesPanel />);
    const inputs = screen.getAllByRole("spinbutton");
    // The first row is X %.
    const input = inputs[0] as HTMLInputElement;
    // React's controlled <input> doesn't pick up direct .value assignments;
    // we use the native setter so React's onChange handler sees the new value.
    const setter = Object.getOwnPropertyDescriptor(
      HTMLInputElement.prototype,
      "value",
    )?.set;
    setter?.call(input, "33");
    input.dispatchEvent(new Event("input", { bubbles: true }));
    const layer = useEditorStore
      .getState()
      .layers.find((l) => l.id === "title");
    expect(layer?.x).toBe(33);
  });
});