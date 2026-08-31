import { useEffect, useMemo, useState } from "react";
import { Plus, Palette, X } from "lucide-react";
import { toast } from "sonner";

import { PageHeader } from "@/components/layout/PageHeader";
import { EmptyState } from "@/components/layout/EmptyState";
import { BrandCard } from "@/components/domain/BrandCard";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { LoadingSkeleton } from "@/components/layout/LoadingSkeleton";
import { cn } from "@/lib/utils";
import {
  useActivateBrand,
  useBrands,
  useCreateBrand,
  useUpdateBrand,
} from "@/lib/query";
import type { Brand } from "@/lib/types";

const emptyDraft = (): Brand => ({
  id: 0,
  name: "",
  tagline: "",
  audience: "",
  palette: [],
  typography: "",
  voice: "",
  do_examples: "",
  dont_examples: "",
  style_guide: "",
  created_at: 0,
  updated_at: 0,
});

export function BrandPage() {
  const brands = useBrands();
  const create = useCreateBrand();
  const update = useUpdateBrand();
  const activate = useActivateBrand();

  const [selectedId, setSelectedId] = useState<number | "new" | null>(null);
  const [draft, setDraft] = useState<Brand>(emptyDraft());
  const [paletteInput, setPaletteInput] = useState("");

  useEffect(() => {
    if (!brands.data) return;
    if (selectedId === null) {
      if (brands.data.brands.length) {
        setSelectedId(brands.data.brands[0].id);
      } else {
        setSelectedId("new");
      }
    }
  }, [brands.data, selectedId]);

  const selected = useMemo(() => {
    if (selectedId === "new") return null;
    return brands.data?.brands.find((b) => b.id === selectedId) ?? null;
  }, [brands.data, selectedId]);

  useEffect(() => {
    if (selected) setDraft(selected);
    if (selectedId === "new") setDraft(emptyDraft());
  }, [selectedId, selected]);

  function patch<K extends keyof Brand>(key: K, value: Brand[K]) {
    setDraft((d) => ({ ...d, [key]: value }));
  }

  function addPalette() {
    const next = paletteInput.trim();
    if (!/^#([0-9a-f]{3}|[0-9a-f]{6})$/i.test(next)) {
      toast.error("Hex must look like #ff6a1f or #f00");
      return;
    }
    if (draft.palette.includes(next.toLowerCase())) {
      toast.error("Already in palette");
      return;
    }
    patch("palette", [...draft.palette, next.toLowerCase()]);
    setPaletteInput("");
  }

  function save() {
    const payload = {
      name: draft.name.trim(),
      tagline: draft.tagline,
      audience: draft.audience,
      palette: draft.palette,
      typography: draft.typography,
      voice: draft.voice,
      do_examples: draft.do_examples,
      dont_examples: draft.dont_examples,
      style_guide: draft.style_guide,
    };
    if (selected) {
      update.mutate(
        { id: selected.id, data: payload },
        {
          onSuccess: (res) => {
            toast.success(`Saved ${res.brand.name}`);
          },
          onError: (err) =>
            toast.error(err instanceof Error ? err.message : "Save failed"),
        },
      );
    } else {
      create.mutate(payload, {
        onSuccess: (res) => {
          toast.success(`Created ${res.brand.name}`);
          setSelectedId(res.brand.id);
        },
        onError: (err) =>
          toast.error(err instanceof Error ? err.message : "Create failed"),
      });
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        meta="Operator · Brand"
        title="Brand profiles"
        description="Brand basics, palette, voice, and do/don't rules. The active brand is auto-prepended to every prompt."
        actions={
          <Button
            variant={selectedId === "new" ? "secondary" : "outline"}
            size="sm"
            onClick={() => setSelectedId("new")}
          >
            <Plus className="h-4 w-4" />
            New brand
          </Button>
        }
      />

      <div className="grid grid-cols-1 gap-6 md:grid-cols-[280px_1fr]">
        <aside className="flex flex-col gap-2">
          {brands.isLoading ? (
            <LoadingSkeleton rows={3} />
          ) : !brands.data?.brands.length ? (
            <EmptyState
              icon={Palette}
              title="No brands yet"
              description="Add a brand so prompts have voice and palette context."
            />
          ) : (
            brands.data.brands.map((b) => (
              <BrandCard
                key={b.id}
                brand={b}
                active={b.id === brands.data.active?.id}
                selected={b.id === selectedId}
                onSelect={() => setSelectedId(b.id)}
              />
            ))
          )}
        </aside>

        <section>
          {selectedId === "new" || selected ? (
            <Card>
              <CardHeader className="flex flex-row items-center justify-between">
                <CardTitle className="text-sm">
                  {selected ? `Edit ${selected.name}` : "New brand"}
                </CardTitle>
                <div className="flex items-center gap-2">
                  {selected &&
                  brands.data?.active?.id !== selected.id ? (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() =>
                        activate.mutate(selected.id, {
                          onSuccess: () =>
                            toast.success(`Activated ${selected.name}`),
                        })
                      }
                    >
                      Set active
                    </Button>
                  ) : null}
                  <Button
                    size="sm"
                    onClick={save}
                    disabled={!draft.name.trim() || create.isPending || update.isPending}
                    data-testid="brand-save"
                  >
                    {selected ? "Save" : "Create"}
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="flex flex-col gap-5">
                <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                  <Field label="Name">
                    <Input
                      value={draft.name}
                      onChange={(e) => patch("name", e.target.value)}
                      placeholder="Gachakingdoms"
                    />
                  </Field>
                  <Field label="Tagline">
                    <Input
                      value={draft.tagline}
                      onChange={(e) => patch("tagline", e.target.value)}
                      placeholder="Pull the blade. Rule the realm."
                    />
                  </Field>
                </div>
                <Field label="Audience">
                  <Input
                    value={draft.audience}
                    onChange={(e) => patch("audience", e.target.value)}
                    placeholder="Collectors of mythic gacha characters"
                  />
                </Field>
                <Field label="Voice">
                  <Input
                    value={draft.voice}
                    onChange={(e) => patch("voice", e.target.value)}
                    placeholder="cinematic, intimate, archival"
                  />
                </Field>
                <Field label="Typography">
                  <Input
                    value={draft.typography}
                    onChange={(e) => patch("typography", e.target.value)}
                    placeholder="Cormorant for display, Inter for body"
                  />
                </Field>
                <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                  <Field label="Do">
                    <Textarea
                      value={draft.do_examples}
                      onChange={(e) => patch("do_examples", e.target.value)}
                      placeholder="tight close-ups, warm light, 35mm grain"
                      rows={4}
                    />
                  </Field>
                  <Field label="Don't">
                    <Textarea
                      value={draft.dont_examples}
                      onChange={(e) => patch("dont_examples", e.target.value)}
                      placeholder="bright saturated backgrounds, stock typography"
                      rows={4}
                    />
                  </Field>
                </div>
                <Field label="Style guide">
                  <Textarea
                    value={draft.style_guide}
                    onChange={(e) => patch("style_guide", e.target.value)}
                    placeholder="Hero always off-axis. Never break the 4th wall."
                    rows={3}
                  />
                </Field>
                <div className="flex flex-col gap-2">
                  <Label>Palette</Label>
                  <div className="flex flex-wrap items-center gap-2">
                    {draft.palette.map((hex) => (
                      <button
                        type="button"
                        key={hex}
                        onClick={() =>
                          patch(
                            "palette",
                            draft.palette.filter((h) => h !== hex),
                          )
                        }
                        className="group flex items-center gap-1 rounded-md border border-border bg-secondary px-2 py-1 text-xs"
                        aria-label={`Remove ${hex}`}
                      >
                        <span
                          className="h-3 w-3 rounded-full border border-border"
                          style={{ background: hex }}
                        />
                        <span className="font-mono text-[11px]">{hex}</span>
                        <X className="h-3 w-3 opacity-50 group-hover:opacity-100" />
                      </button>
                    ))}
                    {draft.palette.length === 0 ? (
                      <Badge variant="muted">no colors yet</Badge>
                    ) : null}
                  </div>
                  <div className="flex items-center gap-2">
                    <Input
                      value={paletteInput}
                      onChange={(e) => setPaletteInput(e.target.value)}
                      placeholder="#ff6a1f"
                      className="max-w-[160px] font-mono"
                    />
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      onClick={addPalette}
                    >
                      Add
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          ) : null}
        </section>
      </div>
    </div>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: import("react").ReactNode;
}) {
  return (
    <div className={cn("flex flex-col gap-2")}>
      <Label>{label}</Label>
      {children}
    </div>
  );
}
