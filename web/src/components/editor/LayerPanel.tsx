import { useEditorStore } from "@/hooks/useEditor";
import type { TemplateLayer } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { Eye, EyeOff, Lock, Unlock, Trash2, GripVertical } from "lucide-react";

type Props = {
  onAddLayer: () => void;
};

const TYPE_LABEL: Record<TemplateLayer["type"], string> = {
  text: "Text",
  image: "Image",
  shape: "Shape",
  ai_background: "AI Background",
  ai_image: "AI Image",
  product_cutout: "Product Cutout",
  video_background: "Video BG",
};

export function LayerPanel({ onAddLayer }: Props) {
  const layers = useEditorStore((s) => s.layers);
  const selection = useEditorStore((s) => s.selection);
  const selectLayer = useEditorStore((s) => s.selectLayer);
  const updateLayerProps = useEditorStore((s) => s.updateLayerProps);
  const removeLayer = useEditorStore((s) => s.removeLayer);
  const reorderLayers = useEditorStore((s) => s.reorderLayers);

  return (
    <aside className="flex w-64 flex-col border-r bg-white">
      <header className="flex items-center justify-between border-b px-3 py-2">
        <h3 className="text-sm font-semibold">Layers</h3>
        <Button size="sm" variant="outline" onClick={onAddLayer}>
          + Add
        </Button>
      </header>

      <ul className="flex-1 overflow-y-auto">
        {layers.length === 0 && (
          <li className="px-3 py-6 text-xs text-muted-foreground">
            No layers yet. Click + Add to create one.
          </li>
        )}
        {layers.map((layer, idx) => {
          const isSelected =
            selection?.kind === "layer" && selection.id === layer.id;
          return (
            <li
              key={layer.id}
              className={cn(
                "group flex items-center gap-2 border-b px-2 py-1.5 text-sm hover:bg-stone-50",
                isSelected && "bg-sky-50",
              )}
              onClick={() => selectLayer(layer.id)}
            >
              <GripVertical className="h-3 w-3 text-stone-400" />
              <div className="flex-1 truncate">
                <div className="truncate font-medium">
                  {layer.name || TYPE_LABEL[layer.type]}
                </div>
                <div className="text-xs text-muted-foreground">
                  {TYPE_LABEL[layer.type]}
                </div>
              </div>
              <button
                aria-label={layer.visible === false ? "Show layer" : "Hide layer"}
                className="opacity-60 hover:opacity-100"
                onClick={(e) => {
                  e.stopPropagation();
                  updateLayerProps(layer.id, {
                    visible: !(layer.visible !== false),
                  });
                }}
              >
                {layer.visible === false ? (
                  <EyeOff className="h-3.5 w-3.5" />
                ) : (
                  <Eye className="h-3.5 w-3.5" />
                )}
              </button>
              <button
                aria-label={layer.locked ? "Unlock layer" : "Lock layer"}
                className="opacity-60 hover:opacity-100"
                onClick={(e) => {
                  e.stopPropagation();
                  updateLayerProps(layer.id, { locked: !layer.locked });
                }}
              >
                {layer.locked ? (
                  <Lock className="h-3.5 w-3.5" />
                ) : (
                  <Unlock className="h-3.5 w-3.5" />
                )}
              </button>
              <div className="flex flex-col">
                <button
                  aria-label="Move up"
                  className="opacity-60 hover:opacity-100 disabled:opacity-20"
                  disabled={idx === 0}
                  onClick={(e) => {
                    e.stopPropagation();
                    reorderLayers(layer.id, idx - 1);
                  }}
                >
                  ▲
                </button>
                <button
                  aria-label="Move down"
                  className="opacity-60 hover:opacity-100 disabled:opacity-20"
                  disabled={idx === layers.length - 1}
                  onClick={(e) => {
                    e.stopPropagation();
                    reorderLayers(layer.id, idx + 1);
                  }}
                >
                  ▼
                </button>
              </div>
              <button
                aria-label="Delete layer"
                className="text-red-500 opacity-0 group-hover:opacity-100"
                onClick={(e) => {
                  e.stopPropagation();
                  removeLayer(layer.id);
                }}
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </li>
          );
        })}
      </ul>
    </aside>
  );
}