import { Check, Star, StarOff, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import {
  useActivateBrand,
  useDeleteBrand,
} from "@/lib/query";
import type { Brand } from "@/lib/types";

export function BrandCard({
  brand,
  active,
  selected,
  onSelect,
}: {
  brand: Brand;
  active: boolean;
  selected: boolean;
  onSelect: () => void;
}) {
  const activate = useActivateBrand();
  const remove = useDeleteBrand();

  return (
    <Card
      data-testid={`brand-card-${brand.id}`}
      className={cn(
        "cursor-pointer transition-colors hover:border-primary/30",
        selected && "border-primary/70 ring-1 ring-primary/50",
      )}
      onClick={onSelect}
    >
      <CardContent className="flex flex-col gap-2 p-4">
        <div className="flex items-center justify-between gap-2">
          <span className="truncate text-sm font-semibold">{brand.name}</span>
          {active ? (
            <Badge variant="default">
              <Check className="h-3 w-3" />
              Active
            </Badge>
          ) : null}
        </div>
        {brand.tagline ? (
          <p className="line-clamp-1 text-xs text-muted-foreground">
            {brand.tagline}
          </p>
        ) : null}
        {brand.palette?.length ? (
          <div className="mt-1 flex items-center gap-1.5">
            {brand.palette.slice(0, 6).map((hex) => (
              <span
                key={hex}
                className="h-3 w-3 rounded-full border border-border"
                style={{ background: hex }}
                title={hex}
              />
            ))}
            <span className="ml-1 font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
              {brand.palette.length}
            </span>
          </div>
        ) : null}
        <div className="mt-2 flex items-center justify-end gap-1.5">
          {!active ? (
            <Button
              size="sm"
              variant="ghost"
              onClick={(e) => {
                e.stopPropagation();
                activate.mutate(brand.id, {
                  onSuccess: () => toast.success(`Activated ${brand.name}`),
                });
              }}
              disabled={activate.isPending}
            >
              <Star className="h-3.5 w-3.5" />
              Activate
            </Button>
          ) : (
            <Button
              size="sm"
              variant="ghost"
              disabled
              className="text-muted-foreground"
            >
              <StarOff className="h-3.5 w-3.5" />
              Active
            </Button>
          )}
          <Button
            size="sm"
            variant="ghost"
            className="text-muted-foreground hover:text-err"
            onClick={(e) => {
              e.stopPropagation();
              if (
                confirm(
                  `Delete brand "${brand.name}"? This cannot be undone.`,
                )
              ) {
                remove.mutate(brand.id, {
                  onSuccess: () => toast.success(`Deleted ${brand.name}`),
                });
              }
            }}
            disabled={remove.isPending}
          >
            <Trash2 className="h-3.5 w-3.5" />
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
