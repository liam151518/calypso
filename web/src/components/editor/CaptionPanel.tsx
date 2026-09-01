import { useEffect, useState } from "react";
import { useEditorStore } from "@/hooks/useEditor";
import {
  useGenerateCaptions,
  useSelectCaption,
  type CaptionVariant,
} from "@/hooks/contentFlow";

export function CaptionPanel() {
  const template = useEditorStore((s) => s.template);
  const product = useEditorStore((s) => s.product);
  const brand = useEditorStore((s) => s.brand);

  const generate = useGenerateCaptions();
  const select = useSelectCaption();
  const [platform, setPlatform] = useState<string>("instagram");
  const [variants, setVariants] = useState<CaptionVariant[]>([]);

  useEffect(() => {
    // Reset when the template/product changes so we don't show stale captions.
    setVariants([]);
  }, [template?.id, product?.id]);

  const onGenerate = () => {
    if (!template?.id || !product?.id) return;
    generate.mutate(
      {
        product_id: Number(product.id),
        template_id: Number(template.id),
        brand_id: brand?.id ?? null,
        platform,
        model: "heuristic",
      },
      {
        onSuccess: (res) => setVariants(res.variants ?? []),
      },
    );
  };

  const onPick = (v: CaptionVariant) => {
    if (!template?.id || !product?.id) return;
    select.mutate({
      output_id: 0, // legacy single-output gate; the editor picks the current render's id later
      variant: v,
      platform,
      brand_id: brand?.id ?? null,
      template_id: typeof template.id === "number" ? template.id : null,
      product_id: typeof product.id === "number" ? product.id : null,
    });
  };

  return (
    <section className="flex flex-col gap-y-2 border-t bg-white px-3 py-2 text-xs">
      <header className="flex items-center justify-between">
        <h3 className="text-sm font-semibold">Captions</h3>
        <select
          value={platform}
          onChange={(e) => setPlatform(e.target.value)}
          className="h-7 rounded border px-2 text-xs"
          aria-label="Caption platform"
        >
          <option value="instagram">Instagram</option>
          <option value="tiktok">TikTok</option>
          <option value="x">X</option>
          <option value="linkedin">LinkedIn</option>
          <option value="facebook">Facebook</option>
        </select>
      </header>

      <div className="flex items-center gap-2">
        <button
          onClick={onGenerate}
          disabled={!template?.id || !product?.id || generate.isPending}
          className="rounded border px-2 py-1 hover:bg-stone-50 disabled:opacity-50"
          data-testid="generate-captions"
        >
          {generate.isPending ? "Generating…" : "Generate 3 captions"}
        </button>
        {variants.length > 0 && (
          <span className="text-muted-foreground">{variants.length} variants</span>
        )}
      </div>

      <ul className="max-h-32 space-y-1 overflow-y-auto">
        {variants.map((v, i) => (
          <li
            key={i}
            className="rounded border bg-stone-50 p-2 hover:bg-stone-100"
            data-testid="caption-variant"
          >
            <div className="line-clamp-2 text-[11px] text-stone-800">{v.content}</div>
            <div className="mt-1 flex items-center justify-between">
              <span className="truncate text-[10px] text-muted-foreground">
                {v.hashtags.slice(0, 3).join(" ")}
              </span>
              <button
                onClick={() => onPick(v)}
                className="rounded border px-2 py-0.5 text-[10px] hover:bg-white"
              >
                Use
              </button>
            </div>
          </li>
        ))}
        {variants.length === 0 && (
          <li className="text-[11px] text-muted-foreground">
            Click "Generate" to draft captions for this template + product.
          </li>
        )}
      </ul>
    </section>
  );
}