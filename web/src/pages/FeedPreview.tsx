import { useState } from "react";
import { useFeed, useShuffleFeed } from "@/hooks/contentFlow";

type Props = {
  brandId?: number | null;
  newOutputId?: number | null;
};

export function FeedPreview({ brandId, newOutputId }: Props) {
  const { data, isLoading } = useFeed(brandId, newOutputId);
  const shuffle = useShuffleFeed();
  const [token, setToken] = useState<string | null>(null);

  const items = data?.items ?? [];

  const onShuffle = () => {
    setToken(crypto.randomUUID());
    shuffle.mutate({ brand_id: brandId ?? null, request_token: token ?? "" });
  };

  if (isLoading) {
    return <div className="p-6 text-sm text-muted-foreground">Loading feed…</div>;
  }

  return (
    <div className="space-y-4">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Feed Preview</h1>
          <p className="text-muted-foreground text-sm">
            Recent outputs in a 3×3 grid. New post (if any) sits in the top-left
            with an orange ring.
          </p>
        </div>
        <button
          onClick={onShuffle}
          disabled={shuffle.isPending}
          className="rounded border px-3 py-1 text-sm hover:bg-stone-50"
        >
          {shuffle.isPending ? "Shuffling…" : "Shuffle"}
        </button>
      </header>

      {items.length === 0 ? (
        <div className="rounded border bg-stone-50 p-6 text-sm text-muted-foreground">
          No outputs yet. Render an image from the Editor to populate the feed.
        </div>
      ) : (
        <div className="grid grid-cols-3 gap-2">
          {items.slice(0, 9).map((item, idx) => {
            const isNew = newOutputId != null && Number(item.id) === Number(newOutputId);
            return (
              <div
                key={item.id}
                className={
                  "aspect-square overflow-hidden rounded bg-stone-100 ring-offset-2 " +
                  (isNew ? "ring-2 ring-orange-500" : "border")
                }
                data-testid="feed-item"
              >
                {item.rel_url ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={item.rel_url}
                    alt={`Output ${item.id}`}
                    className="h-full w-full object-cover"
                  />
                ) : (
                  <div className="flex h-full w-full items-center justify-center text-xs text-stone-400">
                    #{idx}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}