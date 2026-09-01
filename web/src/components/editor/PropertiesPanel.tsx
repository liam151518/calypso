import { useEditorStore } from "@/hooks/useEditor";
import type {
  LayerConfigImage,
  LayerConfigProduct,
  LayerConfigShape,
  LayerConfigText,
  TemplateLayer,
} from "@/lib/types";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

export function PropertiesPanel() {
  const selection = useEditorStore((s) => s.selection);
  const layer = useEditorStore((s) => {
    if (s.selection?.kind !== "layer") return null;
    const sel = s.selection;
    return s.layers.find((l) => l.id === sel.id) ?? null;
  });
  const updateLayerConfig = useEditorStore((s) => s.updateLayerConfig);
  const updateLayerProps = useEditorStore((s) => s.updateLayerProps);

  if (selection?.kind !== "layer" || !layer) {
    return (
      <aside className="flex w-72 flex-col border-l bg-white p-3 text-sm text-muted-foreground">
        Select a layer to edit its properties.
      </aside>
    );
  }

  return (
    <aside className="flex w-72 flex-col gap-y-3 overflow-y-auto border-l bg-white p-3 text-sm">
      <header>
        <h3 className="font-semibold">Properties</h3>
        <p className="text-xs text-muted-foreground">
          {layer.name || layer.type}
        </p>
      </header>

      <Section title="Position">
        <Row label="X %">
          <NumberInput
            value={layer.x ?? 0}
            onChange={(v) => updateLayerProps(layer.id, { x: v })}
          />
        </Row>
        <Row label="Y %">
          <NumberInput
            value={layer.y ?? 0}
            onChange={(v) => updateLayerProps(layer.id, { y: v })}
          />
        </Row>
        <Row label="Width %">
          <NumberInput
            value={layer.width ?? 0}
            onChange={(v) => updateLayerProps(layer.id, { width: v })}
          />
        </Row>
        <Row label="Height %">
          <NumberInput
            value={layer.height ?? 0}
            onChange={(v) => updateLayerProps(layer.id, { height: v })}
          />
        </Row>
        <Row label="Rotation">
          <NumberInput
            value={layer.rotation ?? 0}
            onChange={(v) => updateLayerProps(layer.id, { rotation: v })}
          />
        </Row>
        <Row label="Opacity">
          <NumberInput
            value={layer.opacity ?? 1}
            step={0.05}
            min={0}
            max={1}
            onChange={(v) => updateLayerProps(layer.id, { opacity: v })}
          />
        </Row>
      </Section>

      <ConfigForm layer={layer} onChange={(c) => updateLayerConfig(layer.id, c)} />
    </aside>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded border bg-stone-50 p-2">
      <h4 className="mb-2 text-xs font-semibold uppercase text-muted-foreground">
        {title}
      </h4>
      <div className="space-y-2">{children}</div>
    </section>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-3 items-center gap-2">
      <Label className="text-xs">{label}</Label>
      <div className="col-span-2">{children}</div>
    </div>
  );
}

function NumberInput({
  value,
  onChange,
  step = 1,
  min,
  max,
}: {
  value: number;
  onChange: (v: number) => void;
  step?: number;
  min?: number;
  max?: number;
}) {
  return (
    <Input
      type="number"
      value={Number.isFinite(value) ? Math.round(value * 100) / 100 : 0}
      step={step}
      min={min}
      max={max}
      onChange={(e) => {
        const v = parseFloat(e.target.value);
        if (!Number.isNaN(v)) onChange(v);
      }}
      className="h-7 px-2 text-xs"
    />
  );
}

function ConfigForm({
  layer,
  onChange,
}: {
  layer: TemplateLayer;
  onChange: (config: TemplateLayer["config"]) => void;
}) {
  switch (layer.type) {
    case "text":
      return <TextConfig config={layer.config as LayerConfigText} onChange={onChange} />;
    case "image":
      return <ImageConfig config={layer.config as LayerConfigImage} onChange={onChange} />;
    case "shape":
      return <ShapeConfig config={layer.config as LayerConfigShape} onChange={onChange} />;
    case "product_cutout":
      return <ProductConfig config={layer.config as LayerConfigProduct} onChange={onChange} />;
    case "ai_background":
    case "ai_image":
      return (
        <Section title="AI Prompt">
          <Textarea
            value={(layer.config as { prompt?: string }).prompt ?? ""}
            onChange={(e) =>
              onChange({ ...layer.config, prompt: e.target.value } as TemplateLayer["config"])
            }
            className="min-h-[5rem] text-xs"
          />
        </Section>
      );
    default:
      return null;
  }
}

function TextConfig({
  config,
  onChange,
}: {
  config: LayerConfigText;
  onChange: (c: TemplateLayer["config"]) => void;
}) {
  return (
    <Section title="Text">
      <Row label="Content">
        <Textarea
          value={config.content ?? ""}
          onChange={(e) => onChange({ ...config, content: e.target.value } as TemplateLayer["config"]) }
          className="min-h-[3rem] text-xs"
        />
      </Row>
      <Row label="Font">
        <Input
          value={config.font_family ?? ""}
          onChange={(e) =>
            onChange({ ...config, font_family: e.target.value } as TemplateLayer["config"])
          }
          className="h-7 px-2 text-xs"
        />
      </Row>
      <Row label="Size">
        <NumberInput
          value={config.font_size ?? 32}
          onChange={(v) => onChange({ ...config, font_size: v } as TemplateLayer["config"])}
        />
      </Row>
      <Row label="Color">
        <Input
          type="color"
          value={config.color ?? "#111111"}
          onChange={(e) => onChange({ ...config, color: e.target.value } as TemplateLayer["config"])}
          className="h-7 w-full p-0"
        />
      </Row>
      <Row label="BG">
        <Input
          type="color"
          value={config.background_color ?? "#ffffff"}
          onChange={(e) =>
            onChange({ ...config, background_color: e.target.value } as TemplateLayer["config"])
          }
          className="h-7 w-full p-0"
        />
      </Row>
      <Row label="Align">
        <select
          value={config.text_align ?? "left"}
          onChange={(e) =>
            onChange({
              ...config,
              text_align: e.target.value as LayerConfigText["text_align"],
            } as TemplateLayer["config"])
          }
          className="h-7 rounded border text-xs"
        >
          <option value="left">left</option>
          <option value="center">center</option>
          <option value="right">right</option>
        </select>
      </Row>
    </Section>
  );
}

function ImageConfig({
  config,
  onChange,
}: {
  config: LayerConfigImage;
  onChange: (c: TemplateLayer["config"]) => void;
}) {
  return (
    <Section title="Image">
      <Row label="Src">
        <Input
          value={config.src ?? ""}
          onChange={(e) => onChange({ ...config, src: e.target.value } as TemplateLayer["config"])}
          className="h-7 px-2 text-xs"
        />
      </Row>
      <Row label="Radius">
        <NumberInput
          value={config.border_radius ?? 0}
          onChange={(v) => onChange({ ...config, border_radius: v } as TemplateLayer["config"])}
        />
      </Row>
      <Row label="Fit">
        <select
          value={config.object_fit ?? "cover"}
          onChange={(e) =>
            onChange({
              ...config,
              object_fit: e.target.value as LayerConfigImage["object_fit"],
            } as TemplateLayer["config"])
          }
          className="h-7 rounded border text-xs"
        >
          <option value="cover">cover</option>
          <option value="contain">contain</option>
          <option value="fill">fill</option>
        </select>
      </Row>
    </Section>
  );
}

function ShapeConfig({
  config,
  onChange,
}: {
  config: LayerConfigShape;
  onChange: (c: TemplateLayer["config"]) => void;
}) {
  return (
    <Section title="Shape">
      <Row label="Type">
        <select
          value={config.shape_type}
          onChange={(e) =>
            onChange({
              ...config,
              shape_type: e.target.value as LayerConfigShape["shape_type"],
            } as TemplateLayer["config"])
          }
          className="h-7 rounded border text-xs"
        >
          <option value="rectangle">rectangle</option>
          <option value="circle">circle</option>
          <option value="line">line</option>
        </select>
      </Row>
      <Row label="Fill">
        <Input
          type="color"
          value={config.fill_color ?? "#000000"}
          onChange={(e) => onChange({ ...config, fill_color: e.target.value } as TemplateLayer["config"])}
          className="h-7 w-full p-0"
        />
      </Row>
    </Section>
  );
}

function ProductConfig({
  config,
  onChange,
}: {
  config: LayerConfigProduct;
  onChange: (c: TemplateLayer["config"]) => void;
}) {
  return (
    <Section title="Product">
      <Row label="Slot">
        <select
          value={config.slot ?? "center"}
          onChange={(e) =>
            onChange({
              ...config,
              slot: e.target.value as LayerConfigProduct["slot"],
            } as TemplateLayer["config"])
          }
          className="h-7 rounded border text-xs"
        >
          <option value="center">center</option>
          <option value="left">left</option>
          <option value="right">right</option>
          <option value="top">top</option>
          <option value="bottom">bottom</option>
          <option value="custom">custom</option>
        </select>
      </Row>
      <Row label="Shadow">
        <input
          type="checkbox"
          checked={config.shadow !== false}
          onChange={(e) => onChange({ ...config, shadow: e.target.checked } as TemplateLayer["config"])}
        />
      </Row>
      <Row label="Max W %">
        <NumberInput
          value={config.max_width_percent ?? 60}
          onChange={(v) => onChange({ ...config, max_width_percent: v } as TemplateLayer["config"])}
        />
      </Row>
    </Section>
  );
}