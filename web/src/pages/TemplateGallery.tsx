import { useEffect, useState } from "react";
import {
  useTemplates,
  useBootBuiltins,
  useDuplicateTemplate,
  useDeleteTemplate,
} from "@/hooks/templates";
import type { Template } from "@/lib/types";

export function TemplateGallery() {
  const { data, isLoading, error } = useTemplates();
  const bootBuiltins = useBootBuiltins();
  const duplicate = useDuplicateTemplate();
  const remove = useDeleteTemplate();
  const [activeCategory, setActiveCategory] = useState<string | null>(null);

  // First-time visitors should see built-in templates. Boot them on demand.
  useEffect(() => {
    if (!isLoading && data && data.templates.length === 0 && !bootBuiltins.isPending) {
      bootBuiltins.mutate();
    }
  }, [isLoading, data, bootBuiltins]);

  const templates: Template[] = data?.templates ?? [];
  const categories = Array.from(new Set(templates.map((t) => t.category ?? "other"))).sort();
  const filtered = activeCategory
    ? templates.filter((t) => (t.category ?? "other") === activeCategory)
    : templates;

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Template Gallery</h1>
        <p className="text-muted-foreground text-sm">
          Built-in and custom templates for the brand-poster surface. Click a
          template to view layers; the full WYSIWYG editor lands in Phase B.
        </p>
      </header>

      {isLoading && <div className="text-sm text-muted-foreground">Loading templates…</div>}
      {error && (
        <div className="rounded border border-red-300 bg-red-50 p-3 text-sm text-red-700">
          {String((error as Error).message)}
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        <FilterChip
          label="All"
          active={activeCategory === null}
          onClick={() => setActiveCategory(null)}
        />
        {categories.map((c) => (
          <FilterChip
            key={c}
            label={c}
            active={activeCategory === c}
            onClick={() => setActiveCategory(c)}
          />
        ))}
      </div>

      {filtered.length === 0 && !isLoading && (
        <div className="rounded border border-dashed border-zinc-700 p-8 text-center text-sm text-muted-foreground">
          No templates in this category yet.
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {filtered.map((t) => (
          <TemplateCard
            key={String(t.id)}
            template={t}
            onDuplicate={() =>
              duplicate.mutate({ id: Number(t.id), name: `${t.name} copy` })
            }
            onDelete={() => {
              if (t.is_builtin) return;
              if (confirm(`Delete "${t.name}"?`)) remove.mutate({ id: Number(t.id) });
            }}
          />
        ))}
      </div>
    </div>
  );
}

function FilterChip({
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
      className={
        "rounded-full border px-3 py-1 text-xs " +
        (active
          ? "border-orange-500 bg-orange-500/10 text-orange-300"
          : "border-zinc-700 text-muted-foreground hover:bg-zinc-800")
      }
    >
      {label}
    </button>
  );
}

function TemplateCard({
  template,
  onDuplicate,
  onDelete,
}: {
  template: Template;
  onDuplicate: () => void;
  onDelete: () => void;
}) {
  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-950/40 p-4 shadow-sm transition hover:border-orange-500/50">
      <div className="aspect-square w-full overflow-hidden rounded border border-zinc-800 bg-zinc-900">
        {template.preview_path ? (
          <img
            src={String(template.preview_path)}
            alt={`${template.name} preview`}
            className="h-full w-full object-cover"
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center text-xs text-muted-foreground">
            No preview
          </div>
        )}
      </div>
      <div className="mt-3 flex items-center justify-between">
        <div>
          <div className="font-medium">{template.name}</div>
          <div className="text-xs text-muted-foreground">
            {template.aspect_ratio} · {template.layers.length} layers · {template.category ?? "—"}
          </div>
        </div>
        <div className="flex gap-1">
          <button
            type="button"
            onClick={onDuplicate}
            className="rounded border border-zinc-700 px-2 py-1 text-xs hover:bg-zinc-800"
            title="Duplicate as editable copy"
          >
            Duplicate
          </button>
          {!template.is_builtin && (
            <button
              type="button"
              onClick={onDelete}
              className="rounded border border-red-700 px-2 py-1 text-xs text-red-400 hover:bg-red-900/30"
            >
              Delete
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export default TemplateGallery;