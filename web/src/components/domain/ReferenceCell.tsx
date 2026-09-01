import { useState } from "react";
import { Image as ImageIcon, Trash2, Tag as TagIcon } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { TagPill } from "@/components/layout/TagPill";
import { useDeleteRef, useSetRefTags } from "@/lib/query";
import { formatBytes, cn } from "@/lib/utils";
import type { RefItem } from "@/lib/types";

export function ReferenceCell({ refItem }: { refItem: RefItem }) {
  const ref = refItem;
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState((ref?.tags ?? []).join(", "));
  const setTags = useSetRefTags();
  const remove = useDeleteRef();

  if (!ref) {
    return (
      <Card className="overflow-hidden">
        <CardContent className="p-3 text-xs text-muted-foreground">
          Reference unavailable.
        </CardContent>
      </Card>
    );
  }

  const isVideo = /\.(mp4|mov|webm)$/i.test(ref.ext ?? "");

  return (
    <Card data-testid={`ref-card-${ref.id}`} className="overflow-hidden">
      <div className="relative aspect-square overflow-hidden bg-secondary">
        {isVideo ? (
          <video
            src={ref.rel_url}
            muted
            playsInline
            preload="metadata"
            className="h-full w-full object-cover"
          />
        ) : (
          <img
            src={ref.rel_url}
            alt={ref.name}
            loading="lazy"
            className="h-full w-full object-cover"
          />
        )}
      </div>
      <CardContent className="flex flex-col gap-2 p-3">
        <div className="flex items-center justify-between gap-2">
          <div className="flex min-w-0 items-center gap-1.5">
            <ImageIcon className="h-3 w-3 shrink-0 text-muted-foreground" />
            <span className="truncate font-mono text-xs">{ref.name}</span>
          </div>
          <span className="font-mono text-[10px] text-muted-foreground">
            {formatBytes(ref.size_kb * 1024)}
          </span>
        </div>

        <div className="flex flex-wrap gap-1">
          {ref.tags?.length ? (
            ref.tags.map((t) => <TagPill key={t} tag={t} />)
          ) : (
            <Badge variant="muted">untagged</Badge>
          )}
        </div>

        <div className="flex items-center justify-between gap-1.5 pt-1">
          <Dialog open={editing} onOpenChange={setEditing}>
            <DialogTrigger asChild>
              <Button size="sm" variant="ghost">
                <TagIcon className="h-3.5 w-3.5" />
                Edit tags
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Edit tags</DialogTitle>
                <DialogDescription>{ref.name}</DialogDescription>
              </DialogHeader>
              <Input
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                placeholder="comma, separated, tags"
              />
              <p className="text-xs text-muted-foreground">
                Lowercase, alphanumeric and dashes. Press Save to apply.
              </p>
              <DialogFooter>
                <Button
                  onClick={() => {
                    const next = draft
                      .split(",")
                      .map((s) => s.trim().toLowerCase())
                      .filter(Boolean);
                    setTags.mutate(
                      { id: ref.id, tags: next },
                      {
                        onSuccess: () => {
                          toast.success(`Saved tags for ${ref.name}`);
                          setEditing(false);
                        },
                        onError: (err) =>
                          toast.error(
                            err instanceof Error
                              ? err.message
                              : "Failed to save tags",
                          ),
                      },
                    );
                  }}
                  disabled={setTags.isPending}
                >
                  Save
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>

          <Dialog>
            <DialogTrigger asChild>
              <Button
                size="sm"
                variant="ghost"
                className={cn("text-muted-foreground hover:text-err")}
              >
                <Trash2 className="h-3.5 w-3.5" />
                Delete
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Delete reference?</DialogTitle>
                <DialogDescription>
                  This removes the file and all tag associations. Existing jobs
                  that referenced it will keep the reference id but the file
                  preview will break.
                </DialogDescription>
              </DialogHeader>
              <DialogFooter>
                <Button
                  variant="destructive"
                  onClick={() =>
                    remove.mutate(ref.id, {
                      onSuccess: () =>
                        toast.success(`Deleted ${ref.name}`),
                    })
                  }
                  disabled={remove.isPending}
                >
                  Delete
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>
      </CardContent>
    </Card>
  );
}
