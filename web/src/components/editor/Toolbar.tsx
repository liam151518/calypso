import { useEditorStore, selectCanUndo, selectCanRedo } from "@/hooks/useEditor";
import type { AspectRatio } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Redo2, Undo2, Save, Download, RefreshCcw, Eye, EyeOff } from "lucide-react";

type Props = {
  templateOptions: Array<{ id: number; name: string }>;
  templateId: number | null;
  onTemplateChange: (id: number) => void;
  onSave: () => void;
  onExport: () => void;
  saving?: boolean;
  exporting?: boolean;
  showSafeZones: boolean;
  onToggleSafeZones: () => void;
};

const ASPECT_OPTIONS: AspectRatio[] = ["1:1", "4:5", "9:16", "16:9"];

export function EditorToolbar({
  templateOptions,
  templateId,
  onTemplateChange,
  onSave,
  onExport,
  saving,
  exporting,
  showSafeZones,
  onToggleSafeZones,
}: Props) {
  const aspectRatio = useEditorStore((s) => s.aspectRatio);
  const setAspectRatio = useEditorStore((s) => s.setAspectRatio);
  const undo = useEditorStore((s) => s.undo);
  const redo = useEditorStore((s) => s.redo);
  const reset = useEditorStore((s) => s.reset);
  const dirty = useEditorStore((s) => s.dirty);
  const canUndo = useEditorStore(selectCanUndo);
  const canRedo = useEditorStore(selectCanRedo);

  return (
    <header className="flex h-12 items-center gap-2 border-b bg-white px-3">
      <select
        value={templateId ?? ""}
        onChange={(e) => onTemplateChange(Number(e.target.value))}
        className="h-8 rounded border px-2 text-sm"
        aria-label="Template"
      >
        {templateOptions.map((t) => (
          <option key={t.id} value={t.id}>
            {t.name}
          </option>
        ))}
      </select>

      <div className="mx-2 h-6 w-px bg-stone-200" />

      <div className="flex items-center gap-1" role="radiogroup" aria-label="Aspect ratio">
        {ASPECT_OPTIONS.map((ar) => (
          <button
            key={ar}
            role="radio"
            aria-checked={aspectRatio === ar}
            onClick={() => setAspectRatio(ar)}
            className={
              "h-8 rounded border px-2 text-xs " +
              (aspectRatio === ar
                ? "border-sky-500 bg-sky-50 text-sky-700"
                : "border-stone-200 hover:bg-stone-50")
            }
          >
            {ar}
          </button>
        ))}
      </div>

      <div className="mx-2 h-6 w-px bg-stone-200" />

      <Button
        size="sm"
        variant="outline"
        onClick={undo}
        disabled={!canUndo}
        aria-label="Undo"
        title="Undo"
      >
        <Undo2 className="h-4 w-4" />
      </Button>
      <Button
        size="sm"
        variant="outline"
        onClick={redo}
        disabled={!canRedo}
        aria-label="Redo"
        title="Redo"
      >
        <Redo2 className="h-4 w-4" />
      </Button>
      <Button
        size="sm"
        variant="outline"
        onClick={reset}
        disabled={!dirty}
        aria-label="Reset to template"
        title="Reset"
      >
        <RefreshCcw className="h-4 w-4" />
      </Button>

      <Button
        size="sm"
        variant="outline"
        onClick={onToggleSafeZones}
        aria-label="Toggle safe zones"
        title="Toggle safe zones"
      >
        {showSafeZones ? (
          <Eye className="h-4 w-4" />
        ) : (
          <EyeOff className="h-4 w-4" />
        )}
        <span className="ml-1 text-xs">Safe zones</span>
      </Button>

      <div className="ml-auto flex items-center gap-2">
        <Button size="sm" variant="outline" onClick={onSave} disabled={!dirty || saving}>
          <Save className="mr-1 h-4 w-4" />
          {saving ? "Saving…" : "Save"}
        </Button>
        <Button size="sm" onClick={onExport} disabled={exporting}>
          <Download className="mr-1 h-4 w-4" />
          {exporting ? "Exporting…" : "Export PNG"}
        </Button>
      </div>
    </header>
  );
}