import { ChevronDown, Loader2 } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { StatusPill } from "@/components/layout/StatusPill";
import { useJob } from "@/lib/query";
import { formatRelative } from "@/lib/utils";
import type { Job } from "@/lib/types";

interface JobCardProps {
  job: Job;
  initialOpen?: boolean;
}

export function JobCard({ job, initialOpen }: JobCardProps) {
  // Live updates via TanStack polling. Falls back to seed data on first render.
  const live = useJob(job.id);
  const view = live.data ?? job;

  return (
    <Card data-testid={`job-card-${job.id}`} className="overflow-hidden">
      <CardContent className="flex flex-col gap-3 p-4">
        <div className="flex items-start justify-between gap-3">
          <div className="flex min-w-0 flex-col gap-1">
            <div className="flex items-center gap-2">
              <StatusPill status={view.status} />
              <span className="font-mono text-[11px] text-muted-foreground">
                {view.id}
              </span>
            </div>
            <p className="line-clamp-2 text-sm text-foreground/90">
              {previewPrompt(view.prompt)}
            </p>
          </div>
          <span className="shrink-0 text-[11px] text-muted-foreground">
            {formatRelative(view.elapsed_seconds ? Date.now() / 1000 - view.elapsed_seconds : null)}
          </span>
        </div>

        <div className="flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
          <Badge variant="muted">{view.model}</Badge>
          <Badge variant="muted">{view.duration}s</Badge>
          <Badge variant="muted">{view.resolution}</Badge>
          {view.ref_ids?.length ? (
            <Badge variant="muted">{view.ref_ids.length} refs</Badge>
          ) : null}
        </div>

        {view.status === "running" || view.status === "pending" ? (
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
            Generating…
          </div>
        ) : null}

        {view.status === "succeeded" && view.output_rel ? (
          <video
            src={view.output_rel}
            controls
            preload="metadata"
            className="aspect-video w-full rounded-md border border-border bg-black"
          />
        ) : null}

        {view.status === "failed" && view.error ? (
          <pre className="overflow-auto rounded-md border border-err/30 bg-err/5 p-2 font-mono text-[11px] text-err">
            {view.error}
          </pre>
        ) : null}

        <Collapsible defaultOpen={initialOpen}>
          <CollapsibleTrigger className="inline-flex items-center gap-1.5 text-xs text-muted-foreground transition-colors hover:text-foreground">
            <ChevronDown className="h-3 w-3" />
            Prompt & details
          </CollapsibleTrigger>
          <CollapsibleContent className="mt-2">
            <pre className="overflow-auto rounded-md border border-border bg-secondary p-3 font-mono text-[11px] leading-relaxed text-foreground/90">
              {view.effective_prompt || view.prompt}
            </pre>
            {view.ref_ids?.length ? (
              <div className="mt-2 flex flex-wrap gap-1.5">
                {view.ref_ids.map((rid) => (
                  <Badge key={rid} variant="muted">
                    {rid}
                  </Badge>
                ))}
              </div>
            ) : null}
          </CollapsibleContent>
        </Collapsible>
      </CardContent>
    </Card>
  );
}

function previewPrompt(s: string) {
  if (!s) return "(empty prompt)";
  // Strip the [BRAND]…[/BRAND] prefix from the preview so the user sees the actual ask.
  const stripped = s.replace(/\[BRAND\][\s\S]*?\[\/BRAND\]\s*/g, "");
  const trimmed = stripped.replace(/\[PROMPT\][\s\S]*?\[\/PROMPT\]/g, (m) =>
    m.replace(/^\[PROMPT\]|\[\/PROMPT\]$/g, ""),
  );
  return trimmed.trim().slice(0, 240) || s.slice(0, 240);
}
