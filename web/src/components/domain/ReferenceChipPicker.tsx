import { useMemo, useState } from "react";
import { Check, ImageIcon, X } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";
import { useRefs } from "@/lib/query";
import type { RefItem } from "@/lib/types";

interface ReferenceChipPickerProps {
  selected: string[];
  onChange: (ids: string[]) => void;
}

export function ReferenceChipPicker({
  selected,
  onChange,
}: ReferenceChipPickerProps) {
  const { data, isLoading } = useRefs();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [tagFilter, setTagFilter] = useState<string | null>(null);

  const refs = useMemo(() => data?.refs ?? [], [data?.refs]);
  const tags = useMemo(() => data?.tags ?? [], [data?.tags]);

  const selectedRefs = useMemo(
    () => refs.filter((r) => selected.includes(r.id)),
    [refs, selected],
  );

  const filtered = useMemo(() => {
    return refs.filter((r) => {
      if (tagFilter && !r.tags.includes(tagFilter)) return false;
      if (!query) return true;
      return r.name.toLowerCase().includes(query.toLowerCase());
    });
  }, [refs, query, tagFilter]);

  function toggle(id: string) {
    onChange(
      selected.includes(id) ? selected.filter((x) => x !== id) : [...selected, id],
    );
  }

  return (
    <div className="flex flex-col gap-3" data-testid="reference-chip-picker">
      {selectedRefs.length > 0 ? (
        <div className="flex flex-wrap gap-1.5">
          {selectedRefs.map((r) => (
            <button
              key={r.id}
              type="button"
              onClick={() => toggle(r.id)}
              className="group inline-flex items-center gap-1.5 rounded-md border border-primary/30 bg-primary/10 px-2 py-1 text-xs font-medium text-primary transition-colors hover:bg-primary/20 focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              aria-label={`Remove ${r.name}`}
            >
              <ReferenceThumb refItem={r} />
              <span className="max-w-[12ch] truncate">{r.name}</span>
              <X className="h-3 w-3 opacity-60 group-hover:opacity-100" />
            </button>
          ))}
        </div>
      ) : null}
      <div className="flex flex-wrap items-center gap-2">
        <Popover open={open} onOpenChange={setOpen}>
          <PopoverTrigger asChild>
            <Button variant="outline" size="sm" data-testid="open-ref-picker">
              <ImageIcon className="h-4 w-4" />
              {selected.length > 0 ? `Pick more (${selected.length} selected)` : "Pick references"}
            </Button>
          </PopoverTrigger>
          <PopoverContent className="w-[420px] p-0" align="start">
            <div className="flex flex-col gap-2 p-3">
              <Input
                placeholder="Search references…"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                autoFocus
              />
              {tags.length > 0 ? (
                <div className="flex flex-wrap gap-1">
                  <TagChip
                    label="All"
                    active={tagFilter === null}
                    onClick={() => setTagFilter(null)}
                  />
                  {tags.map((t) => (
                    <TagChip
                      key={t.name}
                      label={`${t.name} · ${t.count}`}
                      active={tagFilter === t.name}
                      onClick={() => setTagFilter(t.name)}
                    />
                  ))}
                </div>
              ) : null}
            </div>
            <ScrollArea className="max-h-[280px] border-t border-border">
              {isLoading ? (
                <div className="p-3 text-sm text-muted-foreground">Loading…</div>
              ) : filtered.length === 0 ? (
                <div className="p-3 text-sm text-muted-foreground">
                  {refs.length === 0
                    ? "Upload references first."
                    : "No references match."}
                </div>
              ) : (
                <ul className="grid grid-cols-3 gap-2 p-3">
                  {filtered.map((r) => {
                    const isSel = selected.includes(r.id);
                    return (
                      <li key={r.id}>
                        <button
                          type="button"
                          onClick={() => toggle(r.id)}
                          aria-pressed={isSel}
                          data-testid={`ref-tile-${r.id}`}
                          className={cn(
                            "group relative flex w-full flex-col items-stretch overflow-hidden rounded-md border border-border bg-card text-left transition-colors hover:border-primary/50 focus:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                            isSel && "border-primary/70 ring-1 ring-primary/50",
                          )}
                        >
                          <div className="flex aspect-square items-center justify-center bg-secondary">
                            <ReferenceThumb refItem={r} className="h-full w-full" />
                          </div>
                          <div className="flex items-center gap-1 px-2 py-1.5">
                            <span className="truncate text-[11px] font-medium">
                              {r.name}
                            </span>
                            {isSel ? (
                              <Check className="ml-auto h-3 w-3 text-primary" />
                            ) : null}
                          </div>
                        </button>
                      </li>
                    );
                  })}
                </ul>
              )}
            </ScrollArea>
          </PopoverContent>
        </Popover>
        {selected.length > 0 ? (
          <Button
            type="button"
            size="sm"
            variant="ghost"
            onClick={() => onChange([])}
            aria-label="Clear references"
          >
            Clear all
          </Button>
        ) : null}
      </div>
    </div>
  );
}

function TagChip({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "rounded-full border border-border bg-secondary px-2 py-0.5 font-mono text-[10px] uppercase tracking-wide transition-colors",
        active && "border-primary/50 bg-primary/10 text-primary",
      )}
    >
      {label}
    </button>
  );
}

function ReferenceThumb({
  refItem,
  className,
}: {
  refItem: RefItem;
  className?: string;
}) {
  if (/\.(mp4|mov|webm)$/i.test(refItem.ext)) {
    return (
      <video
        src={refItem.rel_url}
        muted
        playsInline
        preload="metadata"
        className={cn("h-full w-full object-cover", className)}
      />
    );
  }
  return (
    <img
      src={refItem.rel_url}
      alt={refItem.name}
      className={cn("h-full w-full object-cover", className)}
      loading="lazy"
    />
  );
}

export function ReferenceCount({ count }: { count: number }) {
  return (
    <Badge variant="muted" className="ml-1">
      {count}
    </Badge>
  );
}
