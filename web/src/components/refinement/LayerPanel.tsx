import { useEffect, useState } from "react";
import { Loader2, RefreshCcw, Sparkles, Type } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import type { TemplateLayer } from "@/lib/types";

interface LayerPanelProps {
  layers: TemplateLayer[];
  selectedIndex: number | null;
  onSelect: (index: number) => void;
  isRegenerating: boolean;
  onRegenerate: (payload: {
    prompt?: string;
    seed?: number;
    model?: string;
    text_content?: string;
  }) => void;
}

export function LayerPanel({
  layers,
  selectedIndex,
  onSelect,
  isRegenerating,
  onRegenerate,
}: LayerPanelProps) {
  const selected = selectedIndex !== null ? layers[selectedIndex] : null;

  return (
    <div className="flex flex-col gap-3">
      <ul className="flex flex-col gap-1">
        {layers.length === 0 && (
          <li className="text-xs text-muted-foreground">No layers in this output.</li>
        )}
        {layers.map((l, idx) => {
          const isSelected = idx === selectedIndex;
          return (
            <li key={l.id ?? idx}>
              <button
                type="button"
                onClick={() => onSelect(idx)}
                className={cn(
                  "flex w-full items-center justify-between gap-2 rounded-md border px-2 py-1.5 text-left text-xs transition-colors",
                  isSelected
                    ? "border-primary bg-primary/5 text-foreground"
                    : "border-transparent hover:bg-muted",
                )}
              >
                <span className="flex min-w-0 items-center gap-2">
                  <LayerIcon type={l.type} />
                  <span className="min-w-0 truncate font-medium">
                    {l.name || l.id || `Layer ${idx}`}
                  </span>
                </span>
                <Badge variant="muted" className="shrink-0">
                  {l.type}
                </Badge>
              </button>
            </li>
          );
        })}
      </ul>

      {selected && (
        <LayerEditor
          key={selected.id ?? selectedIndex}
          layer={selected}
          isRegenerating={isRegenerating}
          onRegenerate={onRegenerate}
        />
      )}
    </div>
  );
}

function LayerIcon({ type }: { type: TemplateLayer["type"] }) {
  if (type === "text") return <Type className="h-3.5 w-3.5 text-muted-foreground" />;
  return <Sparkles className="h-3.5 w-3.5 text-muted-foreground" />;
}

function LayerEditor({
  layer,
  isRegenerating,
  onRegenerate,
}: {
  layer: TemplateLayer;
  isRegenerating: boolean;
  onRegenerate: LayerPanelProps["onRegenerate"];
}) {
  const [prompt, setPrompt] = useState("");
  const [seed, setSeed] = useState<string>("");
  const [model, setModel] = useState("");
  const [text, setText] = useState("");

  useEffect(() => {
    // Reset editor state when the selected layer changes.
    const cfg = (layer.config || {}) as Record<string, unknown>;
    setPrompt(typeof cfg.prompt === "string" ? cfg.prompt : "");
    setSeed(typeof cfg.seed === "number" ? String(cfg.seed) : "");
    setModel(typeof cfg.model === "string" ? cfg.model : "");
    setText(typeof cfg.content === "string" ? cfg.content : "");
  }, [layer.id, layer.type]);

  const isAI = layer.type === "ai_background" || layer.type === "ai_image";
  const isText = layer.type === "text";

  function submit() {
    const payload: Parameters<LayerPanelProps["onRegenerate"]>[0] = {};
    if (isAI) {
      if (prompt.trim()) payload.prompt = prompt.trim();
      const parsedSeed = Number(seed);
      if (seed !== "" && Number.isFinite(parsedSeed)) payload.seed = parsedSeed;
      if (model.trim()) payload.model = model.trim();
    }
    if (isText) {
      if (text.trim()) payload.text_content = text.trim();
    }
    if (Object.keys(payload).length === 0) {
      toast.error("Make a change first");
      return;
    }
    onRegenerate(payload);
  }

  return (
    <div className="flex flex-col gap-3 rounded-md border bg-muted/30 p-3">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium">Editing</span>
        <Badge variant="muted">{layer.type}</Badge>
      </div>

      {isAI && (
        <>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="lp-prompt" className="text-[11px]">Prompt</Label>
            <Textarea
              id="lp-prompt"
              rows={3}
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="Describe what to generate"
            />
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="lp-seed" className="text-[11px]">Seed</Label>
              <Input
                id="lp-seed"
                inputMode="numeric"
                value={seed}
                onChange={(e) => setSeed(e.target.value)}
                placeholder="random"
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="lp-model" className="text-[11px]">Model</Label>
              <Input
                id="lp-model"
                value={model}
                onChange={(e) => setModel(e.target.value)}
                placeholder="flux-pro/v1.1"
              />
            </div>
          </div>
        </>
      )}

      {isText && (
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="lp-text" className="text-[11px]">Text</Label>
          <Textarea
            id="lp-text"
            rows={2}
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="New text content"
          />
        </div>
      )}

      {!isAI && !isText && (
        <p className="text-[11px] text-muted-foreground">
          Replace this layer by uploading a new image. Coming soon.
        </p>
      )}

      <Button
        size="sm"
        onClick={submit}
        disabled={isRegenerating || (!isAI && !isText)}
      >
        {isRegenerating ? (
          <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" />
        ) : (
          <RefreshCcw className="mr-1 h-3.5 w-3.5" />
        )}
        Regenerate layer
      </Button>
    </div>
  );
}
