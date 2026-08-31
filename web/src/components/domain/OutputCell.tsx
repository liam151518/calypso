import { useState } from "react";
import { ChevronDown, Download, ImageIcon } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { formatRelative } from "@/lib/utils";
import type { OutputItem } from "@/lib/types";

export function OutputCell({ output }: { output: OutputItem }) {
  const [open, setOpen] = useState(false);
  return (
    <Card data-testid={`output-${output.id}`} className="overflow-hidden">
      <CardContent className="flex flex-col gap-3 p-3">
        <div className="relative aspect-video overflow-hidden rounded-md border border-border bg-black">
          <video
            src={output.rel_url}
            controls
            preload="metadata"
            className="h-full w-full"
          />
        </div>
        <div className="flex items-center justify-between gap-2">
          <div className="flex min-w-0 items-center gap-1.5 font-mono text-[11px] text-muted-foreground">
            <ImageIcon className="h-3 w-3" />
            <span className="truncate">{output.id}</span>
            <span>·</span>
            <span>{output.size_mb} MB</span>
            <span>·</span>
            <span>{formatRelative(output.created)}</span>
          </div>
          <a
            href={output.rel_url}
            download
            className="inline-flex h-7 items-center gap-1 rounded-md border border-border bg-secondary px-2 text-[11px] font-medium text-foreground transition-colors hover:bg-accent"
            aria-label={`Download ${output.id}`}
          >
            <Download className="h-3 w-3" />
            Download
          </a>
        </div>
        <Collapsible open={open} onOpenChange={setOpen}>
          <CollapsibleTrigger className="inline-flex items-center gap-1.5 text-xs text-muted-foreground transition-colors hover:text-foreground">
            <ChevronDown
              className={`h-3 w-3 transition-transform ${open ? "rotate-180" : ""}`}
            />
            Prompt
          </CollapsibleTrigger>
          <CollapsibleContent className="mt-2 space-y-2">
            {(output.brand_name || output.draft_name) && (
              <div className="flex flex-wrap gap-1.5">
                {output.brand_name ? (
                  <Badge variant="default">brand · {output.brand_name}</Badge>
                ) : null}
                {output.draft_name ? (
                  <Badge variant="muted">draft · {output.draft_name}</Badge>
                ) : null}
              </div>
            )}
            <pre className="overflow-auto rounded-md border border-border bg-secondary p-3 font-mono text-[11px] leading-relaxed text-foreground/90">
              {output.prompt || "(no prompt recorded)"}
            </pre>
            {output.refs.length > 0 ? (
              <div className="flex flex-wrap gap-1.5">
                {output.refs.map((r) => (
                  <Badge key={r.id} variant="muted">
                    ref · {r.name}
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
