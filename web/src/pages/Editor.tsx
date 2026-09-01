import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { DndProvider } from "react-dnd";
import { HTML5Backend } from "react-dnd-html5-backend";
import { useQuery } from "@tanstack/react-query";
import { useEditorStore } from "@/hooks/useEditor";
import {
  useTemplates,
  useTemplate,
  useUpdateTemplate,
  useRender,
  useImageOutputs,
} from "@/hooks/templates";
import { api, brandPoster } from "@/lib/api";
import type { Template, TemplateLayer } from "@/lib/types";
import { EditorCanvas } from "@/components/editor/Canvas";
import { LayerPanel } from "@/components/editor/LayerPanel";
import { PropertiesPanel } from "@/components/editor/PropertiesPanel";
import { FilterPanel } from "@/components/editor/FilterPanel";
import { CaptionPanel } from "@/components/editor/CaptionPanel";
import { SchedulePanel } from "@/components/editor/SchedulePanel";
import { EditorToolbar } from "@/components/editor/Toolbar";
import { ExportModal } from "@/components/editor/ExportModal";
import { Button } from "@/components/ui/button";

export function EditorPage() {
  const params = useParams<{ templateId?: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const productIdParam = searchParams.get("productId");
  const productIdNum: number | null = (() => {
    if (!productIdParam) return null;
    const n = Number(productIdParam);
    return Number.isFinite(n) ? n : null;
  })();

  const [showExport, setShowExport] = useState(false);
  const [showSafeZones, setShowSafeZones] = useState(false);

  const templatesQuery = useTemplates();
  const initialId = useMemo(() => {
    if (params.templateId) {
      const n = Number(params.templateId);
      return Number.isFinite(n) ? n : null;
    }
    const first = templatesQuery.data?.templates?.[0]?.id;
    if (typeof first === "number") return first;
    if (typeof first === "string") {
      const n = Number(first);
      return Number.isFinite(n) ? n : null;
    }
    return null;
  }, [params.templateId, templatesQuery.data]);

  const [activeId, setActiveId] = useState<number | null>(initialId ?? null);
  const templateQuery = useTemplate(activeId);
  const productQuery = useProduct(productIdNum);

  const loadTemplate = useEditorStore((s) => s.loadTemplate);
  const template = useEditorStore((s) => s.template);
  const layers = useEditorStore((s) => s.layers);
  const dirty = useEditorStore((s) => s.dirty);
  const filter = useEditorStore((s) => s.filter);
  const intensity = useEditorStore((s) => s.filterIntensity);
  const aspectRatio = useEditorStore((s) => s.aspectRatio);
  const product = useEditorStore((s) => s.product);
  const exporting = useEditorStore((s) => s.exporting);
  const setExporting = useEditorStore((s) => s.setExporting);
  const addLayer = useEditorStore((s) => s.addLayer);

  const updateTemplate = useUpdateTemplate();
  const renderMutation = useRender();
  const outputsQuery = useImageOutputs();

  useEffect(() => {
    if (templatesQuery.data?.templates?.[0]?.id && activeId === null) {
      setActiveId(Number(templatesQuery.data.templates[0].id));
    }
  }, [templatesQuery.data, activeId]);

  useEffect(() => {
    if (!activeId) return;
    let cancelled = false;
    (async () => {
      try {
        const [tmplRes, brandsRes] = await Promise.all([
          brandPoster.getTemplate(activeId),
          api.listBrands(),
        ]);
        if (cancelled) return;
        loadTemplate(
          tmplRes.template as Template,
          (brandsRes as { active?: Brand | null }).active ?? null,
          productQuery.data ?? null,
        );
      } catch {
        if (templateQuery.data && !cancelled) {
          loadTemplate(templateQuery.data as Template, null, productQuery.data ?? null);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [activeId, productQuery.data, templateQuery.data, loadTemplate]);

  const templateOptions = useMemo(
    () =>
      (templatesQuery.data?.templates ?? [])
        .filter((t) => t.id !== undefined)
        .map((t) => ({ id: Number(t.id), name: t.name })),
    [templatesQuery.data],
  );

  const onSave = () => {
    if (!template?.id) return;
    updateTemplate.mutate({
      id: Number(template.id),
      data: {
        layers,
        aspect_ratio: aspectRatio,
        canvas_w: template.canvas?.width,
        canvas_h: template.canvas?.height,
      },
      force: true,
    });
  };

  const onConfirmExport = async (opts: {
    format: "png" | "jpeg";
    quality: number;
    filename: string;
  }) => {
    if (!template?.id) return;
    setExporting(true);
    try {
      const result = await renderMutation.mutateAsync({
        template_id: Number(template.id),
        product_id: product?.id ?? null,
        filter: filter ?? undefined,
        intensity,
        aspect_ratio: aspectRatio,
      });
      const url = result.rel_url;
      if (!url) {
        throw new Error("Render returned no URL");
      }
      const data = await fetch(url).then((r) => r.blob());
      const blobUrl = URL.createObjectURL(data);
      const a = document.createElement("a");
      a.href = blobUrl;
      a.download = opts.filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(blobUrl);
      setShowExport(false);
    } finally {
      setExporting(false);
    }
  };

  const onAddLayer = () => {
    const id = `layer-${Date.now().toString(36)}`;
    const newLayer: TemplateLayer = {
      id,
      type: "text",
      name: "New text",
      x: 20,
      y: 20,
      width: 60,
      height: 12,
      config: {
        content: "Edit me",
        color: "#111111",
        font_size: 48,
        text_align: "center",
      },
    };
    addLayer(newLayer);
  };

  if (templatesQuery.isLoading) {
    return <div className="p-6 text-sm text-muted-foreground">Loading templates…</div>;
  }

  if (!activeId) {
    return (
      <div className="flex h-full items-center justify-center p-6 text-sm text-muted-foreground">
        No templates available.{" "}
        <Button variant="link" onClick={() => navigate("/templates")}>
          Open the Template Gallery
        </Button>{" "}
        to create one.
      </div>
    );
  }

  return (
    <DndProvider backend={HTML5Backend}>
      <div className="flex h-full flex-col">
        <EditorToolbar
          templateOptions={templateOptions}
          templateId={activeId}
          onTemplateChange={setActiveId}
          onSave={onSave}
          onExport={() => setShowExport(true)}
          saving={updateTemplate.isPending}
          exporting={exporting}
          showSafeZones={showSafeZones}
          onToggleSafeZones={() => setShowSafeZones((v) => !v)}
        />

        <div className="flex flex-1 overflow-hidden">
          <LayerPanel onAddLayer={onAddLayer} />
          <EditorCanvas showSafeZones={showSafeZones} />
          <div className="flex w-72 flex-col">
            <PropertiesPanel />
            <FilterPanel />
            <CaptionPanel />
            <SchedulePanel />
          </div>
        </div>

        <footer className="flex h-10 items-center justify-between border-t bg-white px-3 text-xs text-muted-foreground">
          <span>
            {dirty ? "Unsaved changes" : "All changes saved"} · {layers.length} layers
          </span>
          <span>
            Recent outputs:{" "}
            {(outputsQuery.data ?? []).slice(0, 3).map((o) => (
              <a
                key={o.id}
                href={o.rel_url ?? "#"}
                target="_blank"
                rel="noreferrer"
                className="ml-2 underline"
              >
                #{o.id}
              </a>
            ))}
            {!(outputsQuery.data ?? []).length && "none yet"}
          </span>
        </footer>

        <ExportModal
          open={showExport}
          onClose={() => setShowExport(false)}
          onConfirm={onConfirmExport}
          exporting={exporting}
        />
      </div>
    </DndProvider>
  );
}

type Brand = import("@/lib/types").Brand;
type Product = import("@/lib/types").Product;

function useProduct(id: number | null) {
  return useQuery<Product | null, unknown, Product | null>({
    queryKey: ["products", id],
    queryFn: async () => {
      if (!id) return null;
      const r = await brandPoster.getProduct(id);
      return (r.product as Product) ?? null;
    },
    enabled: !!id,
  });
}