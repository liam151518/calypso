import { describe, expect, it, beforeEach, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { buildQueryMock } from "@/test/mocks";

vi.mock("@/lib/query", () => buildQueryMock());

import { LayerPanel } from "./LayerPanel";
import { useEditorStore } from "@/hooks/useEditor";

function makeText(id: string, name: string) {
  return {
    id,
    type: "text" as const,
    name,
    x: 10,
    y: 10,
    width: 50,
    height: 12,
    config: { content: "Hello", color: "#000" },
  };
}

describe("LayerPanel", () => {
  beforeEach(() => {
    // Reset the store between tests.
    useEditorStore.setState((s) => {
      s.template = null;
      s.layers = [];
      s.selection = null;
      s.history = { past: [], future: [] };
      s.dirty = false;
    });
  });

  it("renders the empty state when no layers are loaded", () => {
    render(<LayerPanel onAddLayer={() => undefined} />);
    expect(screen.getByText(/No layers yet/)).toBeInTheDocument();
  });

  it("lists loaded layers by name", () => {
    useEditorStore.setState((s) => {
      s.layers = [makeText("a", "Title"), makeText("b", "Subtitle")];
    });
    render(<LayerPanel onAddLayer={() => undefined} />);
    expect(screen.getByText("Title")).toBeInTheDocument();
    expect(screen.getByText("Subtitle")).toBeInTheDocument();
  });

  it("clicking a layer calls selectLayer", async () => {
    useEditorStore.setState((s) => {
      s.layers = [makeText("a", "Title")];
    });
    render(<LayerPanel onAddLayer={() => undefined} />);
    await userEvent.click(screen.getByText("Title"));
    expect(useEditorStore.getState().selection).toEqual({
      kind: "layer",
      id: "a",
    });
  });

  it("calls onAddLayer when the + Add button is clicked", async () => {
    const onAdd = vi.fn();
    render(<LayerPanel onAddLayer={onAdd} />);
    await userEvent.click(screen.getByRole("button", { name: /\+ Add/ }));
    expect(onAdd).toHaveBeenCalledOnce();
  });

  it("removes a layer when the delete button is clicked", async () => {
    useEditorStore.setState((s) => {
      s.layers = [makeText("a", "Title"), makeText("b", "Subtitle")];
    });
    render(<LayerPanel onAddLayer={() => undefined} />);
    const deleteButtons = screen.getAllByLabelText("Delete layer");
    await userEvent.click(deleteButtons[0]);
    expect(useEditorStore.getState().layers.map((l) => l.id)).toEqual(["b"]);
  });
});