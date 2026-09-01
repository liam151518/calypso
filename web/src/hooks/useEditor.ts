import { create } from "zustand";
import { immer } from "zustand/middleware/immer";
import type {
  AspectRatio,
  Brand,
  Product,
  Template,
  TemplateLayer,
} from "@/lib/types";

export type Selection =
  | { kind: "layer"; id: string }
  | { kind: "canvas" }
  | null;

export type EditorState = {
  template: Template | null;
  product: Product | null;
  brand: Brand | null;
  layers: TemplateLayer[];
  selection: Selection;
  history: { past: TemplateLayer[][]; future: TemplateLayer[][] };
  filter: string | null;
  filterIntensity: number;
  aspectRatio: AspectRatio;
  dirty: boolean;
  exporting: boolean;
};

const HISTORY_LIMIT = 50;

function cloneLayer(layer: TemplateLayer): TemplateLayer {
  return {
    ...layer,
    config: { ...layer.config } as TemplateLayer["config"],
  };
}

function cloneLayers(layers: TemplateLayer[]): TemplateLayer[] {
  return layers.map(cloneLayer);
}

function pushHistory(state: EditorState): void {
  state.history.past.push(cloneLayers(state.layers));
  if (state.history.past.length > HISTORY_LIMIT) {
    state.history.past.shift();
  }
  state.history.future = [];
}

function findLayerIndex(state: EditorState, id: string): number {
  return state.layers.findIndex((l) => l.id === id);
}

export type EditorStore = EditorState & {
  loadTemplate: (
    template: Template,
    brand: Brand | null,
    product: Product | null,
  ) => void;
  selectLayer: (id: string | null) => void;
  selectCanvas: () => void;
  moveLayer: (id: string, x: number, y: number) => void;
  resizeLayer: (
    id: string,
    patch: { x?: number; y?: number; width?: number; height?: number },
  ) => void;
  rotateLayer: (id: string, rotation: number) => void;
  updateLayerConfig: (id: string, config: TemplateLayer["config"]) => void;
  updateLayerProps: (id: string, patch: Partial<TemplateLayer>) => void;
  addLayer: (layer: TemplateLayer, index?: number) => void;
  removeLayer: (id: string) => void;
  reorderLayers: (id: string, toIndex: number) => void;
  setFilter: (filter: string | null, intensity?: number) => void;
  setIntensity: (intensity: number) => void;
  setAspectRatio: (aspect: AspectRatio) => void;
  setDirty: (dirty: boolean) => void;
  setExporting: (exporting: boolean) => void;
  undo: () => void;
  redo: () => void;
  reset: () => void;
};

const initial: EditorState = {
  template: null,
  product: null,
  brand: null,
  layers: [],
  selection: null,
  history: { past: [], future: [] },
  filter: null,
  filterIntensity: 1,
  aspectRatio: "1:1",
  dirty: false,
  exporting: false,
};

export const useEditorStore = create<EditorStore>()(
  immer((set) => ({
    ...initial,

    loadTemplate: (template, brand, product) =>
      set((state) => {
        state.template = template;
        state.brand = brand;
        state.product = product;
        state.layers = cloneLayers(template.layers ?? []);
        state.filter = template.default_filter ?? null;
        state.filterIntensity = 1;
        state.aspectRatio = template.aspect_ratio;
        state.selection = null;
        state.history = { past: [], future: [] };
        state.dirty = false;
        state.exporting = false;
      }),

    selectLayer: (id) =>
      set((state) => {
        state.selection = id ? { kind: "layer", id } : null;
      }),

    selectCanvas: () =>
      set((state) => {
        state.selection = { kind: "canvas" };
      }),

    moveLayer: (id, x, y) =>
      set((state) => {
        const idx = findLayerIndex(state, id);
        if (idx < 0) return;
        pushHistory(state);
        state.layers[idx].x = x;
        state.layers[idx].y = y;
        state.dirty = true;
      }),

    resizeLayer: (id, patch) =>
      set((state) => {
        const idx = findLayerIndex(state, id);
        if (idx < 0) return;
        pushHistory(state);
        const layer = state.layers[idx];
        if (patch.x !== undefined) layer.x = patch.x;
        if (patch.y !== undefined) layer.y = patch.y;
        if (patch.width !== undefined) layer.width = patch.width;
        if (patch.height !== undefined) layer.height = patch.height;
        state.dirty = true;
      }),

    rotateLayer: (id, rotation) =>
      set((state) => {
        const idx = findLayerIndex(state, id);
        if (idx < 0) return;
        pushHistory(state);
        state.layers[idx].rotation = rotation;
        state.dirty = true;
      }),

    updateLayerConfig: (id, config) =>
      set((state) => {
        const idx = findLayerIndex(state, id);
        if (idx < 0) return;
        pushHistory(state);
        state.layers[idx].config = config;
        state.dirty = true;
      }),

    updateLayerProps: (id, patch) =>
      set((state) => {
        const idx = findLayerIndex(state, id);
        if (idx < 0) return;
        pushHistory(state);
        Object.assign(state.layers[idx], patch);
        state.dirty = true;
      }),

    addLayer: (layer, index) =>
      set((state) => {
        pushHistory(state);
        const idx = index ?? state.layers.length;
        state.layers.splice(idx, 0, cloneLayer(layer));
        state.dirty = true;
      }),

    removeLayer: (id) =>
      set((state) => {
        const idx = findLayerIndex(state, id);
        if (idx < 0) return;
        pushHistory(state);
        state.layers.splice(idx, 1);
        if (state.selection?.kind === "layer" && state.selection.id === id) {
          state.selection = null;
        }
        state.dirty = true;
      }),

    reorderLayers: (id, toIndex) =>
      set((state) => {
        const idx = findLayerIndex(state, id);
        if (idx < 0) return;
        if (toIndex < 0 || toIndex >= state.layers.length) return;
        if (idx === toIndex) return;
        pushHistory(state);
        const [moved] = state.layers.splice(idx, 1);
        state.layers.splice(toIndex, 0, moved);
        state.dirty = true;
      }),

    setFilter: (filter, intensity) =>
      set((state) => {
        state.filter = filter;
        if (intensity !== undefined) state.filterIntensity = intensity;
      }),

    setIntensity: (intensity) =>
      set((state) => {
        state.filterIntensity = intensity;
      }),

    setAspectRatio: (aspectRatio) =>
      set((state) => {
        state.aspectRatio = aspectRatio;
      }),

    setDirty: (dirty) =>
      set((state) => {
        state.dirty = dirty;
      }),

    setExporting: (exporting) =>
      set((state) => {
        state.exporting = exporting;
      }),

    undo: () =>
      set((state) => {
        const past = state.history.past;
        if (past.length === 0) return;
        const previous = past.pop()!;
        const future = cloneLayers(state.layers);
        state.layers = previous;
        state.history.future = [...state.history.future, future];
        state.dirty = true;
      }),

    redo: () =>
      set((state) => {
        const future = state.history.future;
        if (future.length === 0) return;
        const next = future.pop()!;
        const past = cloneLayers(state.layers);
        state.layers = next;
        state.history.past = [...state.history.past, past];
        state.dirty = true;
      }),

    reset: () =>
      set((state) => {
        state.layers = cloneLayers(state.template?.layers ?? []);
        state.selection = null;
        state.history = { past: [], future: [] };
        state.dirty = false;
      }),
  })),
);

// Selectors
export const selectCanUndo = (s: EditorStore) => s.history.past.length > 0;
export const selectCanRedo = (s: EditorStore) => s.history.future.length > 0;
export const selectSelectedLayer = (s: EditorStore): TemplateLayer | null => {
  if (s.selection?.kind !== "layer") return null;
  const sel = s.selection;
  return s.layers.find((l) => l.id === sel.id) ?? null;
};