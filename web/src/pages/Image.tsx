import { useState } from "react";
import { ImagePlus, Library } from "lucide-react";
import { toast } from "sonner";

import { PageHeader } from "@/components/layout/PageHeader";
import { BrandBanner } from "@/components/domain/BrandBanner";
import { ReferenceChipPicker } from "@/components/domain/ReferenceChipPicker";
import { ImageComposer } from "@/components/domain/ImageComposer";
import { ImageJobCard } from "@/components/domain/ImageJobCard";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/layout/EmptyState";
import { LoadingSkeleton } from "@/components/layout/LoadingSkeleton";

import { useBrands, useGenerateImage, useImageJobs } from "@/lib/query";

export function ImagePage() {
  const brands = useBrands();
  const generate = useGenerateImage();
  const jobs = useImageJobs();
  const [refIds, setRefIds] = useState<string[]>([]);

  function handleSubmit(
    data: Parameters<typeof generate.mutate>[0],
  ): void {
    generate.mutate(data, {
      onSuccess: () => toast.success("Image job started"),
      onError: (err) =>
        toast.error(err instanceof Error ? err.message : "Failed to start job"),
    });
  }

  const activeRefId = refIds[0] ?? null;

  return (
    <div className="flex flex-col gap-8">
      <PageHeader
        meta="Operator · Image"
        title="Generate an image"
        description="Text-to-image or reference-guided image generation. Use for key art, storyboards, social tiles."
      />

      <BrandBanner />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="flex flex-col gap-4 lg:col-span-2">
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Prompt</CardTitle>
            </CardHeader>
            <CardContent>
              <ImageComposer
                refId={activeRefId}
                onChangeRefId={(id) => setRefIds(id ? [id] : [])}
                brandId={brands.data?.active?.id ?? null}
                isSubmitting={generate.isPending}
                onSubmit={handleSubmit}
              />
            </CardContent>
          </Card>
        </div>

        <div className="flex flex-col gap-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Reference (optional)</CardTitle>
            </CardHeader>
            <CardContent>
              <ReferenceChipPicker
                selected={refIds}
                onChange={(ids) => setRefIds(ids.slice(0, 1))}
              />
              <p className="mt-2 text-[11px] text-muted-foreground">
                Image jobs use a single reference at a time.
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle className="text-sm">Recent image jobs</CardTitle>
              <ImagePlus className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent className="flex flex-col gap-2">
              {jobs.isLoading ? (
                <LoadingSkeleton rows={3} />
              ) : !jobs.data?.length ? (
                <EmptyState
                  icon={Library}
                  title="No image jobs yet"
                  description="Generate an image — recent runs will appear here with live status."
                />
              ) : (
                jobs.data.slice(0, 6).map((j) => (
                  <ImageJobCard key={j.job_id} job={j} />
                ))
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
