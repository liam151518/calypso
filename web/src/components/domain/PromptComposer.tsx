import { useEffect, useState } from "react";
import { Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";

import { ModelPicker } from "./ModelPicker";
import { useEstimateCost, useModels } from "@/lib/query";
import type { CostEstimate, ModelSpec } from "@/lib/types";

interface PromptComposerProps {
  initialPrompt?: string;
  initialDraftId?: number | null;
  refIds: string[];
  brandId?: number | null;
  onDraftChange?: (id: number | null) => void;
  onSubmit: (data: {
    prompt: string;
    model: string;
    duration: number;
    resolution: string;
    ref_ids: string[];
    draft_id: number | null;
    brand_id: number | null;
  }) => void;
  isSubmitting?: boolean;
}

const DURATIONS = [4, 6, 8, 10, 12];
const RESOLUTIONS = ["480p", "768p", "1080p"];

export function PromptComposer({
  initialPrompt = "",
  initialDraftId = null,
  refIds,
  brandId,
  onSubmit,
  isSubmitting,
}: PromptComposerProps) {
  const models = useModels();
  const estimate = useEstimateCost();

  const modelList: ModelSpec[] = models.data?.models ?? [];
  const defaultVideoId = models.data?.defaults.video ?? "minimax/h3";

  const [prompt, setPrompt] = useState(initialPrompt);
  const [model, setModel] = useState(defaultVideoId);
  const [duration, setDuration] = useState(8);
  const [resolution, setResolution] = useState("768p");
  const [cost, setCost] = useState<CostEstimate | null>(null);

  useEffect(() => {
    if (models.data?.defaults.video && model === "minimax/h3") {
      setModel(models.data.defaults.video);
    }
  }, [models.data?.defaults.video, model]);

  // Live estimate: client-side via ModelPicker + server-side debounced via /api/cost-estimate.
  useEffect(() => {
    if (!model) return;
    const handle = window.setTimeout(() => {
      estimate.mutate({
        model,
        duration,
        resolution,
      });
    }, 250);
    return () => window.clearTimeout(handle);
  }, [model, duration, resolution]); // eslint-disable-line react-hooks/exhaustive-deps

  function handleSubmit(e: import("react").FormEvent) {
    e.preventDefault();
    onSubmit({
      prompt: prompt.trim(),
      model,
      duration,
      resolution,
      ref_ids: refIds,
      draft_id: initialDraftId,
      brand_id: brandId ?? null,
    });
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="flex flex-col gap-4"
      data-testid="prompt-composer"
    >
      <div className="flex flex-col gap-2">
        <Label htmlFor="prompt">Prompt</Label>
        <Textarea
          id="prompt"
          name="prompt"
          rows={5}
          required
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="Describe the shot: subject, motion, light, mood…"
          data-testid="prompt-input"
        />
      </div>
      <div className="grid grid-cols-1 items-start gap-3 md:grid-cols-[2fr_1fr_1fr]">
        <div className="min-w-0">
          <ModelPicker
            models={modelList}
            category="video"
            value={model}
            onChange={setModel}
            duration={duration}
            resolution={resolution}
            estimate={estimate.data ?? null}
            onEstimateChange={setCost}
            id="model"
          />
        </div>
        <div className="flex flex-col gap-2">
          <Label htmlFor="duration">Duration</Label>
          <Select
            value={String(duration)}
            onValueChange={(v) => setDuration(Number(v))}
          >
            <SelectTrigger id="duration">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {DURATIONS.map((d) => (
                <SelectItem key={d} value={String(d)}>
                  {d}s
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="flex flex-col gap-2">
          <Label htmlFor="resolution">Resolution</Label>
          <Select value={resolution} onValueChange={setResolution}>
            <SelectTrigger id="resolution">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {RESOLUTIONS.map((r) => (
                <SelectItem key={r} value={r}>
                  {r}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>
      <div className="flex items-center justify-between border-t border-border pt-4">
        <p className="text-xs text-muted-foreground">
          {refIds.length === 0
            ? "No references. Single shot."
            : refIds.length === 1
              ? "1 reference."
              : `Batch of ${refIds.length} references.`}
          {brandId ? " Brand will be prepended." : ""}
          {cost ? (
            <>
              {" "}· Est. <span className="font-mono">${cost.usd.toFixed(3)}</span>
            </>
          ) : null}
        </p>
        <Button
          type="submit"
          disabled={isSubmitting || !prompt.trim()}
          data-testid="submit-generate"
        >
          <Sparkles className="h-4 w-4" />
          {isSubmitting
            ? "Running…"
            : refIds.length > 1
              ? `Run batch (${refIds.length})`
              : "Run generation"}
        </Button>
      </div>
    </form>
  );
}
