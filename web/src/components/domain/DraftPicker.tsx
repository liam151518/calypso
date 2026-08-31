import { useMemo, useState } from "react";
import { Search, Star, StarOff } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from "@/components/ui/command";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import {
  useDeleteDraft,
  useDrafts,
  useFavoriteDraft,
} from "@/lib/query";

interface DraftPickerProps {
  onPick: (draft: { id: number; name: string; body: string }) => void;
}

export function DraftPicker({ onPick }: DraftPickerProps) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState<string | null>(null);
  const [favOnly, setFavOnly] = useState(false);

  const drafts = useDrafts({
    query,
    category: category ?? undefined,
    favorites_only: favOnly,
  });
  const favorite = useFavoriteDraft();

  const cats = drafts.data?.categories ?? [];

  const grouped = useMemo(() => {
    const items = drafts.data?.drafts ?? [];
    const map = new Map<string, typeof items>();
    for (const d of items) {
      const key = d.category || "general";
      if (!map.has(key)) map.set(key, []);
      map.get(key)!.push(d);
    }
    return Array.from(map.entries());
  }, [drafts.data?.drafts]);

  return (
    <>
      <Button
        type="button"
        size="sm"
        variant="outline"
        onClick={() => setOpen(true)}
        data-testid="open-draft-picker"
      >
        <Search className="h-4 w-4" />
        Open drafts
      </Button>
      <CommandDialog open={open} onOpenChange={setOpen}>
        <CommandInput
          placeholder="Search drafts…"
          value={query}
          onValueChange={setQuery}
          autoFocus
        />
        <div className="flex flex-wrap items-center gap-2 border-b border-border px-3 py-2">
          <button
            type="button"
            onClick={() => setFavOnly((v) => !v)}
            className={cn(
              "inline-flex items-center gap-1 rounded-full border border-border bg-secondary px-2 py-0.5 text-[11px] font-medium uppercase tracking-wide transition-colors",
              favOnly && "border-primary/50 bg-primary/10 text-primary",
            )}
          >
            {favOnly ? <Star className="h-3 w-3" /> : <StarOff className="h-3 w-3" />}
            Favorites
          </button>
          <button
            type="button"
            onClick={() => setCategory(null)}
            className={cn(
              "rounded-full border border-border bg-secondary px-2 py-0.5 font-mono text-[10px] uppercase tracking-wide transition-colors",
              category === null && "border-primary/50 bg-primary/10 text-primary",
            )}
          >
            all
          </button>
          {cats.map((c) => (
            <button
              key={c.category}
              type="button"
              onClick={() => setCategory(c.category)}
              className={cn(
                "rounded-full border border-border bg-secondary px-2 py-0.5 font-mono text-[10px] uppercase tracking-wide transition-colors",
                category === c.category && "border-primary/50 bg-primary/10 text-primary",
              )}
            >
              {c.category} · {c.count}
            </button>
          ))}
        </div>
        <CommandList>
          <CommandEmpty>No drafts found.</CommandEmpty>
          {grouped.map(([cat, items], i) => (
            <div key={cat}>
              {i > 0 ? <CommandSeparator /> : null}
              <CommandGroup heading={cat}>
                {items.map((d) => (
                  <CommandItem
                    key={d.id}
                    value={`${d.name} ${d.body}`}
                    onSelect={() => {
                      onPick({ id: d.id, name: d.name, body: d.body });
                      setOpen(false);
                    }}
                    data-testid={`draft-item-${d.id}`}
                  >
                    <div className="flex min-w-0 flex-col">
                      <span className="truncate text-sm font-medium">
                        {d.name}
                      </span>
                      <span className="truncate text-xs text-muted-foreground">
                        {d.body}
                      </span>
                    </div>
                    <div className="ml-auto flex items-center gap-1">
                      {d.is_favorite ? (
                        <Star className="h-3 w-3 fill-current text-primary" />
                      ) : null}
                      <Badge variant="muted" className="ml-1">
                        {d.category || "general"}
                      </Badge>
                    </div>
                  </CommandItem>
                ))}
              </CommandGroup>
            </div>
          ))}
        </CommandList>
        {drafts.data?.drafts?.length ? (
          <div className="flex items-center justify-between border-t border-border px-3 py-2 text-[11px] text-muted-foreground">
            <span>{drafts.data.drafts.length} drafts</span>
            <div className="flex items-center gap-1.5">
              {drafts.data.drafts.slice(0, 3).map((d) => (
                <button
                  key={`fav-${d.id}`}
                  type="button"
                  className="rounded-md border border-border bg-secondary px-2 py-0.5 text-[11px] font-medium transition-colors hover:bg-accent"
                  onClick={() => {
                    favorite.mutate(d.id);
                    toast.success(
                      d.is_favorite ? "Removed from favorites" : "Marked as favorite",
                    );
                  }}
                >
                  <span className="mr-1">{d.is_favorite ? "Unfav" : "Fav"}</span>
                  {d.name}
                </button>
              ))}
            </div>
          </div>
        ) : null}
      </CommandDialog>
    </>
  );
}

export function DraftDeleteButton({
  id,
  name,
}: {
  id: number;
  name: string;
}) {
  const remove = useDeleteDraft();
  return (
    <Button
      size="sm"
      variant="ghost"
      onClick={() => {
        remove.mutate(id, {
          onSuccess: () => toast.success(`Deleted "${name}"`),
        });
      }}
      aria-label={`Delete ${name}`}
    >
      <StarOff className="h-4 w-4" />
    </Button>
  );
}
