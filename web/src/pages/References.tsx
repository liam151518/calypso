import { useMemo, useRef, useState } from "react";
import { Library, Upload } from "lucide-react";
import { toast } from "sonner";

import { PageHeader } from "@/components/layout/PageHeader";
import { EmptyState } from "@/components/layout/EmptyState";
import { LoadingSkeleton } from "@/components/layout/LoadingSkeleton";
import { ReferenceCell } from "@/components/domain/ReferenceCell";
import { TagPill } from "@/components/layout/TagPill";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { useRefs, useUploadRef } from "@/lib/query";

export function ReferencesPage() {
  const refs = useRefs();
  const upload = useUploadRef();
  const [tagFilter, setTagFilter] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [tags, setTags] = useState("");
  const fileInput = useRef<HTMLInputElement>(null);

  const allTags = refs.data?.tags ?? [];
  const items = useMemo(() => {
    const list = refs.data?.refs ?? [];
    if (!tagFilter) return list;
    return list.filter((r) => r.tags.includes(tagFilter));
  }, [refs.data?.refs, tagFilter]);

  function handleUpload() {
    if (!file) return;
    upload.mutate(
      { file, tags: tags.split(",").map((s) => s.trim()).filter(Boolean) },
      {
        onSuccess: () => {
          toast.success(`Uploaded ${file.name}`);
          setFile(null);
          setTags("");
          if (fileInput.current) fileInput.current.value = "";
        },
        onError: (err) =>
          toast.error(err instanceof Error ? err.message : "Upload failed"),
      },
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        meta="Operator · References"
        title="References"
        description="Tag and filter the assets you use as visual seeds. Selections in Generate tag-filter here."
      />

      <Card>
        <CardContent className="grid grid-cols-1 gap-4 p-4 md:grid-cols-[1fr_220px_auto]">
          <div className="flex flex-col gap-2">
            <Label htmlFor="ref-file">Upload</Label>
            <Input
              id="ref-file"
              ref={fileInput}
              type="file"
              accept=".png,.jpg,.jpeg,.webp,.mp4,.mov,.webm"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              data-testid="ref-upload-input"
            />
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="ref-tags">Tags (comma separated)</Label>
            <Input
              id="ref-tags"
              value={tags}
              onChange={(e) => setTags(e.target.value)}
              placeholder="character, hero"
            />
          </div>
          <div className="flex items-end">
            <Button
              onClick={handleUpload}
              disabled={!file || upload.isPending}
              data-testid="ref-upload-submit"
            >
              <Upload className="h-4 w-4" />
              {upload.isPending ? "Uploading…" : "Upload"}
            </Button>
          </div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 gap-6 md:grid-cols-[200px_1fr]">
        <aside className="flex flex-col gap-2">
          <div className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
            Tags
          </div>
          <button
            type="button"
            onClick={() => setTagFilter(null)}
            className={cn(
              "rounded-md border border-border bg-secondary px-2 py-1.5 text-left text-xs transition-colors",
              tagFilter === null && "border-primary/50 bg-primary/10 text-primary",
            )}
          >
            All ({refs.data?.refs.length ?? 0})
          </button>
          {allTags.map((t) => (
            <button
              key={t.name}
              type="button"
              onClick={() => setTagFilter(t.name)}
              className={cn(
                "flex items-center justify-between rounded-md border border-border bg-secondary px-2 py-1.5 text-left text-xs transition-colors",
                tagFilter === t.name && "border-primary/50 bg-primary/10 text-primary",
              )}
            >
              <TagPill tag={t.name} />
              <span className="font-mono text-[10px] text-muted-foreground">
                {t.count}
              </span>
            </button>
          ))}
        </aside>

        <section>
          {refs.isLoading ? (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {Array.from({ length: 4 }).map((_, i) => (
                <LoadingSkeleton key={i} rows={2} />
              ))}
            </div>
          ) : !items.length ? (
            <EmptyState
              icon={Library}
              title="No references uploaded"
              description="Upload your first reference to get started. Tag it so it shows up in the right filter on Generate."
              actionLabel="Upload"
              onAction={() => fileInput.current?.click()}
            />
          ) : (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {items.map((r) => (
                <ReferenceCell key={r.id} ref={r} />
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
