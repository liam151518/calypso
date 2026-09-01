import { Palette, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useBrands,
  useClearActiveBrand,
} from "@/lib/query";
import type { Brand } from "@/lib/types";

export function BrandBanner() {
  const { data, isLoading } = useBrands();
  const clear = useClearActiveBrand();

  if (isLoading) return <BrandBannerSkeleton />;
  if (!data?.active) return <BrandBannerEmpty />;

  return (
    <Card data-testid="brand-banner">
      <CardContent className="flex flex-col gap-3 p-4 md:flex-row md:items-center md:justify-between">
        <div className="flex items-start gap-3">
          <div className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary">
            <Palette className="h-4 w-4" />
          </div>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm font-semibold tracking-tight">
                {data.active.name}
              </span>
              <span className="text-xs text-muted-foreground">
                {data.active.tagline || "Active brand"}
              </span>
            </div>
            <PaletteRow brand={data.active} />
          </div>
        </div>
        <Button
          size="sm"
          variant="ghost"
          onClick={() => clear.mutate()}
          disabled={clear.isPending}
          aria-label="Clear active brand"
        >
          <X className="h-4 w-4" />
          Clear
        </Button>
      </CardContent>
    </Card>
  );
}

function PaletteRow({ brand }: { brand: Brand }) {
  if (!brand.palette?.length) return null;
  return (
    <div className="mt-2 flex items-center gap-1.5">
      {brand.palette.slice(0, 6).map((hex) => (
        <span
          key={hex}
          className="h-3 w-3 rounded-full border border-border"
          style={{ background: hex }}
          title={hex}
        />
      ))}
      <span className="ml-2 font-mono text-[11px] uppercase tracking-wide text-muted-foreground">
        {brand.palette.length} colors
      </span>
    </div>
  );
}

function BrandBannerSkeleton() {
  return (
    <Card>
      <CardContent className="flex items-center gap-3 p-4">
        <Skeleton className="h-9 w-9 rounded-md" />
        <div className="flex-1 space-y-2">
          <Skeleton className="h-3.5 w-32" />
          <Skeleton className="h-2.5 w-48" />
        </div>
      </CardContent>
    </Card>
  );
}

function BrandBannerEmpty() {
  return (
    <Card>
      <CardContent className="flex items-center gap-3 p-4 text-sm text-muted-foreground">
        <div className="flex h-9 w-9 items-center justify-center rounded-md bg-secondary">
          <Palette className="h-4 w-4" />
        </div>
        No active brand. Add one on the Brand page. It will be auto-prepended
        to every prompt.
      </CardContent>
    </Card>
  );
}
