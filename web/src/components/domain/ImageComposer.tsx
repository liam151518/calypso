import { useEffect, useState } from "react";
import { ImagePlus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

import { ModelPicker } from "./ModelPicker";
import { useEstimateCost, useGenerateImage, useModels } from "@/lib/query";
import type { CostEstimate, ModelSpec } from "@/lib/types";

type GenerateImagePayload = Parameters<ReturnType<typeof useGenerateImage>["mutate"]>[0];

interface ImageComposerProps {
  refId: string | null;
  onChangeRefId: (id: string | null) => void;
  brandId?: number | null;
  onSubmit: (data: GenerateImagePayload) => void;
  isSubmitting?: boolean;
}

const ASPECT_RATIOS = ["1:1", "16:9", "9:16", "4:3", "3:4"];

export function ImageComposer({
  refId,
  brandId,
  onSubmit,
  isSubmitting,
}: ImageComposerProps) {
  const models = useModels();
  const estimate = useEstimateCost();

  const modelList: ModelSpec[] = models.data?.models ?? [];
  const defaultImageId = models.data?.defaults.image ?? "flux-pro/v1.1";

  const [prompt, setPrompt] = useState("");
  const [model, setModel] = useState(defaultImageId);
  const [aspectRatio, setAspectRatio] = useState("1:1");
  const [numImages, setNumImages] = useState(1);
  const [cost, setCost] = useState<CostEstimate | null>(null);

  useEffect(() => {
    if (models.data?.defaults.image && model === "flux-pro/v1.1") {
      setModel(models.data.defaults.image);
    }
  }, [models.data?.defaults.image, model]);

  useEffect(() => {
    if (!model) return;
    const handle = window.setTimeout(() => {
      estimate.mutate({
        model,
        aspect_ratio: aspectRatio,
        num_images: numImages,
      });
    }, 250);
    return () => window.clearTimeout(handle);
  }, [model, aspectRatio, numImages]); // eslint-disable-line react-hooks/exhaustive-deps

  function handleSubmit(e: import("react").FormEvent) {
    e.preventDefault();
    onSubmit({
      prompt: prompt.trim(),
      model,
      aspect_ratio: aspectRatio,
      num_images: numImages,
      ref_id: refId,
      brand_id: brandId ?? null,
    });
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="flex flex-col gap-4"
      data-testid="image-composer"
    >
      <div className="flex flex-col gap-2">
        <Label htmlFor="img-prompt">Prompt</Label>
        <Textarea
          id="img-prompt"
          rows={4}
          required
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="Hero product shot, soft key light, neutral backdrop…"
          data-testid="image-prompt-input"
        />
      </div>
      <div className="grid grid-cols-1 items-start gap-3 md:grid-cols-[2fr_1fr_1fr]">
        <div className="min-w-0">
          <ModelPicker
            models={modelList}
            category="image"
            value={model}
            onChange={setModel}
            aspect_ratio={aspectRatio}
            num_images={numImages}
            estimate={estimate.data ?? null}
            onEstimateChange={setCost}
            id="img-model"
          />
        </div>
        <div className="flex flex-col gap-2">
          <Label htmlFor="img-aspect">Aspect</Label>
          <select
            id="img-aspect"
            value={aspectRatio}
            onChange={(e) => setAspectRatio(e.target.value)}
            className="h-10 rounded-md border border-input bg-background px-3 text-sm"
            data-testid="image-aspect-select"
          >
            {ASPECT_RATIOS.map((a) => (
              <option key={a} value={a}>
                {a}
              </option>
            ))}
          </select>
        </div>
        <div className="flex flex-col gap-2">
          <Label htmlFor="img-num"># images</Label>
          <select
            id="img-num"
            value={String(numImages)}
            onChange={(e) => setNumImages(Math.max(1, Number(e.target.value)))}
            className="h-10 rounded-md border border-input bg-background px-3 text-sm"
            data-testid="image-num-select"
          >
            {[1, 2, 3, 4].map((n) => (
              <option key={n} value={String(n)}>
                {n}
              </option>
            ))}
          </select>
        </div>
      </div>
      <div className="flex items-center justify-between border-t border-border pt-4">
        <p className="text-xs text-muted-foreground">
          {refId ? `1 reference: ${refId}` : "No reference. Text-to-image."}
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
          data-testid="submit-image"
        >
          <ImagePlus className="h-4 w-4" />
          {isSubmitting ? "Rendering…" : "Generate image"}
        </Button>
      </div>
    </form>
  );
}
