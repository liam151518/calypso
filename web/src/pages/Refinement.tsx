import { useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Layers, Sliders, Wand2 } from "lucide-react";
import { toast } from "sonner";

import { PageHeader } from "@/components/layout/PageHeader";
import { EmptyState } from "@/components/layout/EmptyState";
import { LoadingSkeleton } from "@/components/layout/LoadingSkeleton";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";

import {
  useRefinementOutput,
  useOutputVersions,
  useRegenerateLayer,
  useUpscaleOutput,
  usePromoteVersion,
  useDeleteVersion,
} from "@/lib/query";
import type { OutputVersion, TemplateLayer } from "@/lib/types";
import { LayerPanel } from "@/components/refinement/LayerPanel";
import { RefinePanel } from "@/components/refinement/RefinePanel";

export function RefinementPage() {
  const params = useParams<{ outputId: string }>();
  const navigate = useNavigate();
  const id = Number(params.outputId);
  const validId = Number.isFinite(id) && id > 0;

  const outputQuery = useRefinementOutput(validId ? id : 0);
  const versionsQuery = useOutputVersions(validId ? id : 0);

  const regen = useRegenerateLayer(validId ? id : 0);
  const upscale = useUpscaleOutput(validId ? id : 0);
  const promote = usePromoteVersion(validId ? id : 0);
  const delVersion = useDeleteVersion(validId ? id : 0);

  const output = outputQuery.data?.output ?? null;
  const versions = (versionsQuery.data?.versions ?? []) as OutputVersion[];

  // Selected layer (index into layers array)
  const [selectedLayer, setSelectedLayer] = useState<number | null>(null);
  // Selected version (when comparing)
  const [compareVersionId, setCompareVersionId] = useState<number | null>(null);

  const compareVersion = useMemo(
    () => versions.find((v) => v.id === compareVersionId) ?? null,
    [versions, compareVersionId],
  );

  function handleRegenerate(payload: {
    prompt?: string;
    seed?: number;
    model?: string;
    text_content?: string;
  }) {
    if (selectedLayer === null) return;
    regen.mutate(
      { layerIndex: selectedLayer, payload },
      {
        onSuccess: () => toast.success("Layer regenerated"),
        onError: (err) =>
          toast.error(err instanceof Error ? err.message : "Failed"),
      },
    );
  }

  function handleUpscale(scale: 2 | 4, model: "realesrgan" | "fal") {
    upscale.mutate(
      { scale, model },
      {
        onSuccess: (res) =>
          toast.success(
            `Upscaled to ${res.upscale.width}×${res.upscale.height} via ${res.upscale.model_used}`,
          ),
        onError: (err) =>
          toast.error(err instanceof Error ? err.message : "Upscale failed"),
      },
    );
  }

  function handlePromote(versionId: number) {
    promote.mutate(versionId, {
      onSuccess: () => toast.success("Promoted to current"),
      onError: (err) =>
        toast.error(err instanceof Error ? err.message : "Promote failed"),
    });
  }

  function handleDeleteVersion(versionId: number) {
    delVersion.mutate(versionId, {
      onSuccess: () => toast.success("Version deleted"),
      onError: (err) =>
        toast.error(err instanceof Error ? err.message : "Delete failed"),
    });
  }

  if (!validId) {
    return (
      <EmptyState
        title="Invalid output id"
        description="Pick an output from the Outputs page to start refining."
      />
    );
  }
  if (outputQuery.isLoading) {
    return (
      <div className="flex flex-col gap-6">
        <PageHeader meta="Refinement Studio" title="Loading…" />
        <LoadingSkeleton rows={3} />
      </div>
    );
  }
  if (!output) {
    return (
      <EmptyState
        title="Output not found"
        description="It may have been deleted. Head back to Outputs."
        actionLabel="Back to outputs"
        onAction={() => navigate("/outputs")}
      />
    );
  }

  const layers = (output.layers || []) as TemplateLayer[];
  const previewUrl = output.rel_url;
  const compareUrl = compareVersion?.rel_url ?? null;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-start justify-between gap-4">
        <PageHeader
          meta="Refinement Studio"
          title={`Output #${output.id}`}
          description="Edit layers, upscale, compare versions. Promote a version to make it the canonical render."
        />
        <Button asChild variant="outline" size="sm">
          <Link to="/outputs">
            <ArrowLeft className="mr-2 h-3.5 w-3.5" />
            Back to outputs
          </Link>
        </Button>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[16rem_minmax(0,1fr)_22rem]">
        {/* LEFT: layer panel */}
        <Card className="self-start">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-sm">
              <Layers className="h-4 w-4" />
              Layers
              <Badge variant="muted" className="ml-auto">
                {layers.length}
              </Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <LayerPanel
              layers={layers}
              selectedIndex={selectedLayer}
              onSelect={setSelectedLayer}
              isRegenerating={regen.isPending}
              onRegenerate={handleRegenerate}
            />
          </CardContent>
        </Card>

        {/* CENTER: canvas / preview */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-sm">
              <Wand2 className="h-4 w-4" />
              Preview
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-col gap-4">
              {previewUrl ? (
                <CompareSurface
                  primaryUrl={previewUrl}
                  compareUrl={compareUrl}
                />
              ) : (
                <EmptyState
                  title="No preview available"
                  description="The output's file isn't on disk."
                />
              )}
              <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                <Badge variant="muted">{output.type}</Badge>
                {output.aspect_ratio && (
                  <Badge variant="muted">{output.aspect_ratio}</Badge>
                )}
                {output.filter_applied && (
                  <Badge variant="muted">filter: {output.filter_applied}</Badge>
                )}
                {output.cost_usd ? (
                  <Badge variant="muted">${output.cost_usd.toFixed(3)}</Badge>
                ) : null}
              </div>
            </div>
          </CardContent>
        </Card>

        {/* RIGHT: refine panel */}
        <Card className="self-start">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-sm">
              <Sliders className="h-4 w-4" />
              Refine
            </CardTitle>
          </CardHeader>
          <CardContent>
            <Tabs defaultValue="quality" className="w-full">
              <TabsList className="grid w-full grid-cols-3">
                <TabsTrigger value="quality">Quality</TabsTrigger>
                <TabsTrigger value="variants">Variants</TabsTrigger>
                <TabsTrigger value="vfx">VFX</TabsTrigger>
              </TabsList>
              <TabsContent value="quality" className="mt-4">
                <RefinePanel
                  mode="quality"
                  isUpscaling={upscale.isPending}
                  onUpscale={handleUpscale}
                />
              </TabsContent>
              <TabsContent value="variants" className="mt-4">
                <RefinePanel
                  mode="variants"
                  versions={versions}
                  compareVersionId={compareVersionId}
                  onCompare={setCompareVersionId}
                  onPromote={handlePromote}
                  onDelete={handleDeleteVersion}
                />
              </TabsContent>
              <TabsContent value="vfx" className="mt-4">
                <RefinePanel mode="vfx" />
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function CompareSurface({
  primaryUrl,
  compareUrl,
}: {
  primaryUrl: string;
  compareUrl: string | null;
}) {
  if (!compareUrl) {
    return (
      <img
        src={primaryUrl}
        alt="Output preview"
        className="mx-auto max-h-[520px] w-auto rounded-md border bg-muted"
      />
    );
  }
  return (
    <div className="grid grid-cols-2 gap-2">
      <div className="flex flex-col gap-1">
        <span className="text-[11px] uppercase tracking-wide text-muted-foreground">
          Current
        </span>
        <img
          src={primaryUrl}
          alt="Current"
          className="max-h-[400px] w-full rounded-md border bg-muted object-contain"
        />
      </div>
      <div className="flex flex-col gap-1">
        <span className="text-[11px] uppercase tracking-wide text-muted-foreground">
          Compare
        </span>
        <img
          src={compareUrl}
          alt="Compare"
          className="max-h-[400px] w-full rounded-md border bg-muted object-contain"
        />
      </div>
    </div>
  );
}
