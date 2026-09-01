import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import {
  Preset,
  useCreatePreset,
  useDeletePreset,
  usePresets,
} from "@/hooks/presets";

export interface PresetManagerProps {
  brandId?: number | null;
}

export function PresetManager({ brandId }: PresetManagerProps) {
  const presetsQ = usePresets(brandId);
  const create = useCreatePreset();
  const del = useDeletePreset();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [templateId, setTemplateId] = useState("");
  const [filterName, setFilterName] = useState("bright");
  const [productFilter, setProductFilter] = useState("");

  const submit = () => {
    if (!name.trim()) return;
    create.mutate({
      brand_id: brandId ?? null,
      name: name.trim(),
      description: description.trim() || null,
      template_id: templateId ? parseInt(templateId, 10) : null,
      filter: filterName || null,
      product_filter: productFilter
        ? (() => {
            try {
              return JSON.parse(productFilter);
            } catch {
              return {};
            }
          })()
        : {},
    });
    setName("");
    setDescription("");
  };

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-semibold">Presets</h1>
        <p className="text-sm text-slate-500">
          Save a winning template + filter + product filter combination.
          Re-run it against any set of products with one click.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">New preset</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label htmlFor="p-name">Name</Label>
              <Input
                id="p-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Auto-sneaker-drop"
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="p-tpl">Template ID</Label>
              <Input
                id="p-tpl"
                value={templateId}
                onChange={(e) => setTemplateId(e.target.value)}
                placeholder="optional"
              />
            </div>
          </div>
          <div className="space-y-1">
            <Label htmlFor="p-desc">Description</Label>
            <Textarea
              id="p-desc"
              rows={2}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="What is this preset for?"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label htmlFor="p-filter">Filter</Label>
              <select
                id="p-filter"
                className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
                value={filterName}
                onChange={(e) => setFilterName(e.target.value)}
              >
                <option value="">none</option>
                <option value="bright">bright</option>
                <option value="moody">moody</option>
                <option value="vintage">vintage</option>
                <option value="minimal">minimal</option>
                <option value="neon">neon</option>
              </select>
            </div>
            <div className="space-y-1">
              <Label htmlFor="p-pf">Product filter (JSON)</Label>
              <Input
                id="p-pf"
                value={productFilter}
                onChange={(e) => setProductFilter(e.target.value)}
                placeholder='{"category": "shoes"}'
              />
            </div>
          </div>
          <Button
            onClick={submit}
            disabled={!name.trim() || create.isPending}
          >
            <Plus className="mr-2 h-4 w-4" />
            Save preset
          </Button>
        </CardContent>
      </Card>

      <div>
        <h2 className="text-sm font-medium uppercase tracking-wide text-slate-500 mb-2">
          Saved presets ({presetsQ.data?.presets?.length ?? 0})
        </h2>
        {presetsQ.data?.presets?.length ? (
          <ul className="space-y-2">
            {presetsQ.data.presets.map((p: Preset) => (
              <li
                key={p.id}
                className="flex items-start justify-between rounded-md border border-slate-200 bg-white p-3"
              >
                <div>
                  <div className="font-medium">{p.name}</div>
                  {p.description && (
                    <div className="text-sm text-slate-500">{p.description}</div>
                  )}
                  <div className="mt-1 text-xs text-slate-400">
                    template #{p.template_id ?? "—"} · filter {p.filter ?? "none"}
                  </div>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => del.mutate(p.id)}
                  aria-label={`Delete ${p.name}`}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </li>
            ))}
          </ul>
        ) : (
          <div className="rounded-md border border-dashed border-slate-300 p-6 text-center text-sm text-slate-500">
            No presets yet.
          </div>
        )}
      </div>
    </div>
  );
}

export default PresetManager;