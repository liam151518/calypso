import { useEffect, useState } from "react";
import { Sparkles, Library } from "lucide-react";
import { toast } from "sonner";

import { PageHeader } from "@/components/layout/PageHeader";
import { BrandBanner } from "@/components/domain/BrandBanner";
import { ReferenceChipPicker } from "@/components/domain/ReferenceChipPicker";
import { DraftPicker } from "@/components/domain/DraftPicker";
import { PromptComposer } from "@/components/domain/PromptComposer";
import { JobCard } from "@/components/domain/JobCard";
import { BatchBlock } from "@/components/domain/BatchBlock";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/layout/EmptyState";
import { LoadingSkeleton } from "@/components/layout/LoadingSkeleton";
import { useGenerate, useJobs, useBrands } from "@/lib/query";
import type { Job } from "@/lib/types";

export function GeneratePage() {
  const brands = useBrands();
  const generate = useGenerate();
  const jobs = useJobs();

  const [prompt, setPrompt] = useState("");
  const [draftId, setDraftId] = useState<number | null>(null);
  const [refIds, setRefIds] = useState<string[]>([]);
  const [recentJobs, setRecentJobs] = useState<Job[]>([]);
  const [recentBatches, setRecentBatches] = useState<
    { batchId: string; jobs: Job[] }[]
  >([]);

  // Reset draft context when prompt body diverges from draft body.
  useEffect(() => {
    if (draftId == null) return;
    // Keep draft id as-is; server is tolerant of stale refs.
  }, [prompt, draftId]);

  function handleSubmit(data: Parameters<typeof generate.mutate>[0]) {
    setPrompt(data.prompt);
    generate.mutate(data, {
      onSuccess: (res) => {
        if (res.kind === "batch" && res.jobs) {
          toast.success(`Batch started (${res.jobs.length} jobs)`);
          setRecentBatches((prev) => [
            { batchId: res.batch_id!, jobs: res.jobs! },
            ...prev,
          ].slice(0, 5));
        } else if (res.kind === "job" && res.job) {
          toast.success("Job started");
          setRecentJobs((prev) => [res.job!, ...prev].slice(0, 10));
        }
      },
      onError: (err) => {
        toast.error(err instanceof Error ? err.message : "Failed to start job");
      },
    });
  }

  return (
    <div className="flex flex-col gap-8">
      <PageHeader
        meta="Operator · Generate"
        title="Compose a generation"
        description="Pick a brand, choose references, draft a prompt. Run a single shot or a batch."
      />

      <BrandBanner />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="flex flex-col gap-4 lg:col-span-2">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between gap-3">
              <CardTitle className="text-sm">Prompt</CardTitle>
              <DraftPicker
                onPick={(d) => {
                  setPrompt(d.body);
                  setDraftId(d.id);
                }}
              />
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              <PromptComposer
                initialPrompt={prompt}
                initialDraftId={draftId}
                refIds={refIds}
                brandId={brands.data?.active?.id ?? null}
                isSubmitting={generate.isPending}
                onSubmit={handleSubmit}
              />
            </CardContent>
          </Card>

          {(recentJobs.length > 0 || recentBatches.length > 0) && (
            <section className="flex flex-col gap-3">
              <h2 className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                Just launched
              </h2>
              {recentJobs.map((j) => (
                <JobCard key={j.id} job={j} />
              ))}
              {recentBatches.map((b) => (
                <BatchBlock key={b.batchId} batchId={b.batchId} jobs={b.jobs} />
              ))}
            </section>
          )}
        </div>

        <div className="flex flex-col gap-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">References</CardTitle>
            </CardHeader>
            <CardContent>
              <ReferenceChipPicker
                selected={refIds}
                onChange={setRefIds}
              />
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle className="text-sm">Recent jobs</CardTitle>
              <Sparkles className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent className="flex flex-col gap-2">
              {jobs.isLoading ? (
                <LoadingSkeleton rows={3} />
              ) : !jobs.data?.length ? (
                <EmptyState
                  icon={Library}
                  title="No jobs yet"
                  description="Generate something — recent runs will appear here with live status."
                />
              ) : (
                jobs.data.slice(0, 6).map((j) => (
                  <JobCard key={j.id} job={j} initialOpen />
                ))
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
