import { useState } from "react";
import {
  ArrowUpRightFromSquare,
  Loader2,
  Star,
  Trash2,
  ZoomIn,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";
import type { OutputVersion } from "@/lib/types";

type Mode = "quality" | "variants" | "vfx";

interface RefinePanelProps {
  mode: Mode;
  // Quality
  isUpscaling?: boolean;
  onUpscale?: (scale: 2 | 4, model: "realesrgan" | "fal") => void;
  // Variants
  versions?: OutputVersion[];
  compareVersionId?: number | null;
  onCompare?: (versionId: number | null) => void;
  onPromote?: (versionId: number) => void;
  onDelete?: (versionId: number) => void;
}

export function RefinePanel({
  mode,
  isUpscaling = false,
  onUpscale,
  versions = [],
  compareVersionId = null,
  onCompare,
  onPromote,
  onDelete,
}: RefinePanelProps) {
  if (mode === "quality") {
    return <QualityTab isUpscaling={isUpscaling} onUpscale={onUpscale} />;
  }
  if (mode === "variants") {
    return (
      <VariantsTab
        versions={versions}
        compareVersionId={compareVersionId}
        onCompare={onCompare}
        onPromote={onPromote}
        onDelete={onDelete}
      />
    );
  }
  return <VfxTab />;
}

// ---- Quality ----------------------------------------------------------

function QualityTab({
  isUpscaling,
  onUpscale,
}: {
  isUpscaling: boolean;
  onUpscale?: (scale: 2 | 4, model: "realesrgan" | "fal") => void;
}) {
  const [model, setModel] = useState<"realesrgan" | "fal">("realesrgan");
  const [faceEnhance, setFaceEnhance] = useState(false);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-2">
        <span className="text-xs font-medium">Upscale</span>
        <div className="grid grid-cols-2 gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={isUpscaling || !onUpscale}
            onClick={() => onUpscale?.(2, model)}
          >
            {isUpscaling ? <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" /> : <ZoomIn className="mr-1 h-3.5 w-3.5" />}
            2x
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={isUpscaling || !onUpscale}
            onClick={() => onUpscale?.(4, model)}
          >
            {isUpscaling ? <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" /> : <ZoomIn className="mr-1 h-3.5 w-3.5" />}
            4x
          </Button>
        </div>
      </div>

      <div className="flex flex-col gap-2">
        <Label className="text-[11px]">Backend</Label>
        <div className="flex gap-1 rounded-md border p-0.5 text-xs">
          {(["realesrgan", "fal"] as const).map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => setModel(m)}
              className={cn(
                "flex-1 rounded px-2 py-1 text-center transition-colors",
                model === m ? "bg-primary/10 text-primary" : "text-muted-foreground hover:text-foreground",
              )}
            >
              {m}
            </button>
          ))}
        </div>
      </div>

      <div className="flex items-center justify-between">
        <Label htmlFor="face-enhance" className="text-xs">Face enhancement</Label>
        <Switch
          id="face-enhance"
          checked={faceEnhance}
          onCheckedChange={setFaceEnhance}
        />
      </div>

      <p className="text-[11px] text-muted-foreground">
        Real-ESRGAN runs locally (free). <code>fal</code> uses fal.ai's ESRGAN
        endpoint (paid, ~$0.04/MP).
      </p>
    </div>
  );
}

// ---- Variants ---------------------------------------------------------

function VariantsTab({
  versions,
  compareVersionId,
  onCompare,
  onPromote,
  onDelete,
}: {
  versions: OutputVersion[];
  compareVersionId: number | null;
  onCompare?: (versionId: number | null) => void;
  onPromote?: (versionId: number) => void;
  onDelete?: (versionId: number) => void;
}) {
  if (versions.length === 0) {
    return (
      <p className="text-xs text-muted-foreground">
        No saved versions yet. Regenerate a layer or upscale to create one.
      </p>
    );
  }
  return (
    <ul className="flex flex-col gap-2">
      {versions.map((v) => {
        const isCompare = v.id === compareVersionId;
        return (
          <li
            key={v.id}
            className={cn(
              "flex flex-col gap-1 rounded-md border p-2 text-xs transition-colors",
              isCompare ? "border-primary bg-primary/5" : "border-border",
            )}
          >
            <div className="flex items-center justify-between gap-2">
              <span className="font-medium">v{v.id}</span>
              <Badge variant="muted" className="shrink-0">
                ${(v.cost_usd ?? 0).toFixed(3)}
              </Badge>
            </div>
            <span className="line-clamp-2 text-[11px] text-muted-foreground">
              {v.notes || "No notes"}
            </span>
            <div className="flex flex-wrap items-center gap-1.5">
              <Button
                size="sm"
                variant="ghost"
                onClick={() => onCompare?.(isCompare ? null : v.id)}
                aria-pressed={isCompare}
              >
                {isCompare ? "Comparing" : "Compare"}
              </Button>
              {onPromote && (
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => onPromote(v.id)}
                  title="Make this the canonical render"
                >
                  <Star className="mr-1 h-3 w-3" />
                  Promote
                </Button>
              )}
              {onDelete && (
                <Button
                  size="sm"
                  variant="ghost"
                  className="text-err hover:text-err"
                  onClick={() => onDelete(v.id)}
                >
                  <Trash2 className="mr-1 h-3 w-3" />
                  Delete
                </Button>
              )}
              <Button
                size="sm"
                variant="ghost"
                asChild
                className="ml-auto"
              >
                <a href={v.rel_url ?? v.file_path} target="_blank" rel="noreferrer">
                  <ArrowUpRightFromSquare className="mr-1 h-3 w-3" />
                  Open
                </a>
              </Button>
            </div>
          </li>
        );
      })}
    </ul>
  );
}

// ---- VFX --------------------------------------------------------------

function VfxTab() {
  return (
    <div className="flex flex-col gap-2">
      <p className="text-xs text-muted-foreground">
        VFX timeline editing applies to video outputs. Drag scene blocks,
        shift motion-graphic timing, pick an easing curve.
      </p>
      <p className="text-[11px] text-muted-foreground">
        <Badge variant="muted">video</Badge>{" "}
        Coming once the video refinement backend lands (Phase D+).
      </p>
    </div>
  );
}
