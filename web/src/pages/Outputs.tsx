import { Clapperboard, ImagePlus } from "lucide-react";

import { PageHeader } from "@/components/layout/PageHeader";
import { EmptyState } from "@/components/layout/EmptyState";
import { LoadingSkeleton } from "@/components/layout/LoadingSkeleton";
import { OutputCell } from "@/components/domain/OutputCell";
import { useImageOutputs, useOutputs } from "@/lib/query";

export function OutputsPage() {
  const outputs = useOutputs();
  const imageOutputs = useImageOutputs();

  const totalCount = (outputs.data?.length ?? 0) + (imageOutputs.data?.length ?? 0);
  const isLoading = outputs.isLoading || imageOutputs.isLoading;

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        meta="Operator · Outputs"
        title="Generated outputs"
        description="Past video and image runs with their effective prompts, brand context, and source references."
      />
      {isLoading ? (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <LoadingSkeleton key={i} rows={2} />
          ))}
        </div>
      ) : totalCount === 0 ? (
        <EmptyState
          icon={Clapperboard}
          title="No outputs yet"
          description="Generate on the Generate or Image page — outputs will appear here once they finish."
        />
      ) : (
        <div className="flex flex-col gap-8">
          {outputs.data && outputs.data.length > 0 ? (
            <section className="flex flex-col gap-3">
              <h2 className="flex items-center gap-2 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                <Clapperboard className="h-3.5 w-3.5" /> Videos
              </h2>
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
                {outputs.data.map((o) => (
                  <OutputCell key={o.id} output={o} />
                ))}
              </div>
            </section>
          ) : null}
          {imageOutputs.data && imageOutputs.data.length > 0 ? (
            <section className="flex flex-col gap-3">
              <h2 className="flex items-center gap-2 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                <ImagePlus className="h-3.5 w-3.5" /> Images
              </h2>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
                {imageOutputs.data.map((o) => (
                  <a
                    key={o.id}
                    href={o.rel_url}
                    target="_blank"
                    rel="noreferrer"
                    className="group flex flex-col gap-2 rounded-md border border-border bg-card p-2 transition-colors hover:border-primary"
                  >
                    <div className="aspect-square overflow-hidden rounded bg-secondary">
                      <img
                        src={o.rel_url}
                        alt={o.prompt}
                        className="h-full w-full object-cover transition-transform group-hover:scale-105"
                      />
                    </div>
                    <p className="line-clamp-2 text-xs">{o.prompt}</p>
                    <div className="flex flex-wrap items-center gap-1.5 text-[10px] text-muted-foreground">
                      <span className="font-mono">{o.model}</span>
                      <span>·</span>
                      <span>{o.aspect_ratio}</span>
                      {o.cost_usd != null ? (
                        <>
                          <span>·</span>
                          <span className="font-mono">
                            ${o.cost_usd.toFixed(3)}
                          </span>
                        </>
                      ) : null}
                    </div>
                  </a>
                ))}
              </div>
            </section>
          ) : null}
        </div>
      )}
    </div>
  );
}
