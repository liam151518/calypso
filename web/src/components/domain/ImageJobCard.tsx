import { useEffect, useState } from "react";
import { Coins, Image as ImageIcon, X } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogTrigger,
} from "@/components/ui/dialog";
import { StatusPill } from "@/components/layout/StatusPill";
import { useImageJob } from "@/lib/query";
import type { ImageJob } from "@/lib/types";

interface ImageJobCardProps {
  job: ImageJob;
  initialOpen?: boolean;
}

function formatUSD(n: number | null | undefined): string {
  if (n === null || n === undefined || Number.isNaN(n)) return "n/a";
  return `$${n.toFixed(n < 0.1 ? 3 : 2)}`;
}

export function ImageJobCard({ job, initialOpen = false }: ImageJobCardProps) {
  const live = useImageJob(job.job_id);
  const current = live.data ?? job;
  const [open, setOpen] = useState(initialOpen);

  // Reset open state when job_id changes so the dialog doesn't stay open.
  useEffect(() => {
    setOpen(initialOpen);
  }, [job.job_id, initialOpen]);

  const firstImage = current.output_paths?.[0];
  const previewSrc = firstImage
    ? firstImage.replace(
        /^.*\/outputs\//,
        "/outputs/file/",
      )
    : current.output_rel ?? null;

  return (
    <div
      data-testid={`image-job-${current.job_id}`}
      className="flex flex-col gap-2 rounded-md border border-border bg-card p-3 text-sm"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex min-w-0 flex-col gap-1">
          <StatusPill status={current.status} />
          <p className="line-clamp-2 font-mono text-xs">{current.prompt}</p>
          <div className="flex flex-wrap items-center gap-1.5 text-[10px] text-muted-foreground">
            <Badge variant="muted" className="font-mono">
              {current.model}
            </Badge>
            <Badge variant="muted">{current.aspect_ratio}</Badge>
            <Badge variant="muted">{current.num_images} img</Badge>
            {current.cost_usd != null ? (
              <Badge variant="outline" className="gap-1 font-mono">
                <Coins className="h-3 w-3" />
                {formatUSD(current.cost_usd)}
              </Badge>
            ) : null}
          </div>
        </div>
      </div>

      {current.error ? (
        <p className="text-xs text-destructive">{current.error}</p>
      ) : null}

      {previewSrc ? (
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <button
              type="button"
              className="group relative aspect-square overflow-hidden rounded-md border border-border bg-secondary"
              data-testid={`image-job-preview-${current.job_id}`}
            >
              <img
                src={previewSrc}
                alt={current.prompt}
                className="h-full w-full object-cover transition-transform group-hover:scale-105"
              />
            </button>
          </DialogTrigger>
          <DialogContent className="max-w-4xl border-border bg-card p-0">
            <div className="relative">
              <Button
                variant="ghost"
                size="icon"
                className="absolute right-2 top-2 z-10 h-8 w-8 rounded-full bg-background/80"
                onClick={() => setOpen(false)}
              >
                <X className="h-4 w-4" />
              </Button>
              <img
                src={previewSrc}
                alt={current.prompt}
                className="max-h-[80vh] w-full rounded-md object-contain"
              />
            </div>
            <div className="border-t border-border p-4">
              <p className="line-clamp-3 text-sm">{current.prompt}</p>
              <p className="mt-2 font-mono text-[10px] text-muted-foreground">
                {current.job_id} · {current.model} · {current.aspect_ratio}
              </p>
            </div>
          </DialogContent>
        </Dialog>
      ) : current.status === "running" || current.status === "queued" ? (
        <div className="flex aspect-square items-center justify-center rounded-md border border-border bg-secondary text-xs text-muted-foreground">
          <ImageIcon className="mr-2 h-4 w-4 animate-pulse" />
          {current.status === "queued" ? "queued" : "rendering…"}
        </div>
      ) : null}
    </div>
  );
}
