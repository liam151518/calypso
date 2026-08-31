import { useState } from "react";
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

const MODELS = [
  { value: "auto", label: "Auto" },
  { value: "minimax/h3", label: "MiniMax H3" },
  { value: "fal/minimax-video", label: "fal · minimax" },
  { value: "fal/kling-video", label: "fal · kling" },
];

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
  const [prompt, setPrompt] = useState(initialPrompt);
  const [model, setModel] = useState("auto");
  const [duration, setDuration] = useState(8);
  const [resolution, setResolution] = useState("768p");

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
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <div className="flex flex-col gap-2">
          <Label htmlFor="model">Model</Label>
          <Select value={model} onValueChange={setModel}>
            <SelectTrigger id="model">
              <SelectValue placeholder="Auto" />
            </SelectTrigger>
            <SelectContent>
              {MODELS.map((m) => (
                <SelectItem key={m.value} value={m.value}>
                  {m.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
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
            ? "No references — single shot."
            : refIds.length === 1
              ? "1 reference."
              : `Batch of ${refIds.length} references.`}
          {brandId ? " Brand will be prepended." : ""}
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
