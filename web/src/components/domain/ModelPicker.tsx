import { useEffect, useMemo, useState } from "react";
import { Check, ChevronsUpDown, Coins, Sparkles } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { Label } from "@/components/ui/label";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { cn } from "@/lib/utils";
import type { CostEstimate, ModelSpec } from "@/lib/types";

interface ModelPickerProps {
  models: ModelSpec[];
  category: "video" | "image";
  value: string;
  onChange: (id: string) => void;
  // For video: live cost estimate depends on duration/resolution.
  duration?: number;
  resolution?: string;
  aspect_ratio?: string;
  num_images?: number;
  estimate?: CostEstimate | null;
  onEstimateChange?: (est: CostEstimate | null) => void;
  id?: string;
}

function formatUSD(n: number | null | undefined): string {
  if (n === null || n === undefined || Number.isNaN(n)) return "n/a";
  return `$${n.toFixed(n < 0.1 ? 3 : 2)}`;
}

export function ModelPicker({
  models,
  category,
  value,
  onChange,
  duration,
  resolution,
  aspect_ratio,
  num_images = 1,
  estimate: externalEstimate,
  onEstimateChange,
  id,
}: ModelPickerProps) {
  const filtered = useMemo(
    () => models.filter((m) => m.category === category),
    [models, category],
  );
  const current = useMemo(
    () => filtered.find((m) => m.id === value) ?? null,
    [filtered, value],
  );

  const [open, setOpen] = useState(false);

  // Lightweight client-side estimate (used immediately for snappy UX).
  const localEstimate = useMemo<CostEstimate | null>(() => {
    if (!current) return null;
    if (category === "video") {
      const dur = duration ?? 8;
      const res = resolution ?? "768p";
      const rate = current.per_second_usd[res] ?? 0.05;
      return {
        usd: +(rate * dur).toFixed(4),
        model_id: current.id,
        category: "video",
        duration: dur,
        resolution: res,
      };
    }
    const ar = aspect_ratio ?? "1:1";
    return {
      usd: +(current.per_image_usd * Math.max(1, num_images)).toFixed(4),
      model_id: current.id,
      category: "image",
      aspect_ratio: ar,
      num_images,
    };
  }, [current, category, duration, resolution, aspect_ratio, num_images]);

  useEffect(() => {
    onEstimateChange?.(localEstimate);
  }, [localEstimate, onEstimateChange]);

  return (
    <div className="flex flex-col gap-2" data-testid={`model-picker-${category}`}>
      <Label htmlFor={id}>Model</Label>
      <div className="flex items-center gap-2">
        <Popover open={open} onOpenChange={setOpen}>
          <PopoverTrigger asChild>
            <Button
              id={id}
              variant="outline"
              role="combobox"
              aria-expanded={open}
              className="w-full justify-between font-normal"
              data-testid={`model-picker-trigger-${category}`}
            >
              {current ? (
                <span className="flex items-center gap-2 truncate">
                  <Sparkles className="h-4 w-4 text-primary" />
                  <span className="truncate font-medium">{current.name}</span>
                  {current.badge ? (
                    <Badge variant="muted" className="ml-1">
                      {current.badge}
                    </Badge>
                  ) : null}
                </span>
              ) : (
                <span className="text-muted-foreground">Pick a model…</span>
              )}
              <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
            </Button>
          </PopoverTrigger>
          <PopoverContent className="w-[420px] p-0" align="start">
            <Command>
              <CommandInput placeholder="Search models…" />
              <CommandList>
                <CommandEmpty>No models match.</CommandEmpty>
                <CommandGroup heading={`${category === "video" ? "Video" : "Image"} models`}>
                  {filtered.map((m) => (
                    <CommandItem
                      key={m.id}
                      value={`${m.name} ${m.vendor} ${m.id}`}
                      onSelect={() => {
                        onChange(m.id);
                        setOpen(false);
                      }}
                      className="flex items-start gap-2"
                      data-testid={`model-option-${m.id}`}
                    >
                      <Check
                        className={cn(
                          "mt-1 h-4 w-4 shrink-0",
                          m.id === value ? "opacity-100" : "opacity-0",
                        )}
                      />
                      <div className="flex min-w-0 flex-col gap-0.5">
                        <div className="flex items-center gap-2">
                          <span className="font-medium">{m.name}</span>
                          {m.badge ? (
                            <Badge variant="muted">{m.badge}</Badge>
                          ) : null}
                          {m.is_default ? (
                            <Badge variant="default">default</Badge>
                          ) : null}
                        </div>
                        <span className="font-mono text-[10px] text-muted-foreground">
                          {m.vendor} · {m.id}
                        </span>
                        {m.description ? (
                          <span className="line-clamp-2 text-xs text-muted-foreground">
                            {m.description}
                          </span>
                        ) : null}
                      </div>
                    </CommandItem>
                  ))}
                </CommandGroup>
              </CommandList>
            </Command>
          </PopoverContent>
        </Popover>
      </div>
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span className="truncate">
          {current?.description ?? "Pick a model to see cost."}
        </span>
        <Badge
          variant="outline"
          className="ml-2 shrink-0 gap-1 font-mono"
          data-testid={`model-cost-${category}`}
        >
          <Coins className="h-3 w-3" />
          {formatUSD(externalEstimate?.usd ?? localEstimate?.usd)}
        </Badge>
      </div>
    </div>
  );
}
