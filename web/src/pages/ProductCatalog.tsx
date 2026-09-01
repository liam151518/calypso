import { useState } from "react";
import {
  useProducts,
  useCreateProduct,
  useDeleteProduct,
  useImportProducts,
  useCutout,
} from "@/hooks/products";
import type { Product } from "@/lib/types";

export function ProductCatalog() {
  const { data, isLoading, error } = useProducts();
  const create = useCreateProduct();
  const remove = useDeleteProduct();
  const importCsv = useImportProducts();
  const cutout = useCutout();
  const products: Product[] = data?.products ?? [];

  const [draft, setDraft] = useState({
    name: "",
    price: "",
    category: "",
    description: "",
    image_path: "",
  });
  const [csvDraft, setCsvDraft] = useState("");

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Product Catalog</h1>
        <p className="text-muted-foreground text-sm">
          Add products individually or import a CSV. Cutout generation uses rembg
          in the background — click “Regenerate cutout” after swapping an image.
        </p>
      </header>

      {error && (
        <div className="rounded border border-red-300 bg-red-50 p-3 text-sm text-red-700">
          {String((error as Error).message)}
        </div>
      )}

      <section className="rounded-lg border border-zinc-800 bg-zinc-950/40 p-4">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          Add product
        </h2>
        <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
          <input
            type="text"
            placeholder="Name"
            value={draft.name}
            onChange={(e) => setDraft({ ...draft, name: e.target.value })}
            className="rounded border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm"
          />
          <input
            type="number"
            placeholder="Price (ZAR)"
            value={draft.price}
            onChange={(e) => setDraft({ ...draft, price: e.target.value })}
            className="rounded border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm"
          />
          <input
            type="text"
            placeholder="Category (apparel, footwear, …)"
            value={draft.category}
            onChange={(e) => setDraft({ ...draft, category: e.target.value })}
            className="rounded border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm"
          />
          <input
            type="text"
            placeholder="Image path (relative to project root)"
            value={draft.image_path}
            onChange={(e) => setDraft({ ...draft, image_path: e.target.value })}
            className="rounded border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm"
          />
        </div>
        <textarea
          placeholder="Description"
          value={draft.description}
          onChange={(e) => setDraft({ ...draft, description: e.target.value })}
          className="mt-2 w-full rounded border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm"
          rows={2}
        />
        <button
          type="button"
          disabled={!draft.name || create.isPending}
          onClick={() =>
            create.mutate({
              name: draft.name,
              price: draft.price ? Number(draft.price) : null,
              category: draft.category || null,
              description: draft.description || null,
              image_path: draft.image_path || null,
              tags: [],
            })
          }
          className="mt-2 rounded bg-orange-600 px-3 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          {create.isPending ? "Saving…" : "Add product"}
        </button>
      </section>

      <section className="rounded-lg border border-zinc-800 bg-zinc-950/40 p-4">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          CSV import
        </h2>
        <p className="mb-2 text-xs text-muted-foreground">
          Columns: name, price, category, collection, description, image_path, launch_date, tags (|` separated)
        </p>
        <textarea
          value={csvDraft}
          onChange={(e) => setCsvDraft(e.target.value)}
          rows={4}
          placeholder="name,price,category,description,image_path,tags"
          className="w-full rounded border border-zinc-700 bg-zinc-900 px-3 py-2 text-xs font-mono"
        />
        <button
          type="button"
          disabled={!csvDraft || importCsv.isPending}
          onClick={() =>
            importCsv.mutate({ csv: csvDraft }, {
              onSuccess: () => setCsvDraft(""),
            })
          }
          className="mt-2 rounded border border-orange-600 px-3 py-2 text-sm font-medium text-orange-300 disabled:opacity-50"
        >
          {importCsv.isPending ? "Importing…" : "Import CSV"}
        </button>
      </section>

      <section>
        {isLoading && <div className="text-sm text-muted-foreground">Loading products…</div>}
        {!isLoading && products.length === 0 && (
          <div className="rounded border border-dashed border-zinc-700 p-8 text-center text-sm text-muted-foreground">
            No products yet. Add one above or import a CSV.
          </div>
        )}
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {products.map((p) => (
            <div
              key={p.id}
              className="rounded-lg border border-zinc-800 bg-zinc-950/40 p-3"
            >
              <div className="aspect-square overflow-hidden rounded border border-zinc-800 bg-zinc-900">
                {p.image_path ? (
                  <img
                    src={p.image_path}
                    alt={p.name}
                    className="h-full w-full object-cover"
                  />
                ) : (
                  <div className="flex h-full w-full items-center justify-center text-xs text-muted-foreground">
                    No image
                  </div>
                )}
              </div>
              <div className="mt-2 flex items-start justify-between">
                <div>
                  <div className="font-medium">{p.name}</div>
                  <div className="text-xs text-muted-foreground">
                    {p.price ? `R${p.price.toFixed(2)}` : "—"} · {p.category ?? "—"}
                  </div>
                </div>
                <div className="flex flex-col gap-1">
                  <button
                    type="button"
                    disabled={!p.image_path || cutout.isPending}
                    onClick={() => cutout.mutate({ id: p.id, regenerate: true })}
                    className="rounded border border-zinc-700 px-2 py-1 text-xs hover:bg-zinc-800 disabled:opacity-50"
                  >
                    Regenerate cutout
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      if (confirm(`Delete "${p.name}"?`)) remove.mutate(p.id);
                    }}
                    className="rounded border border-red-700 px-2 py-1 text-xs text-red-400 hover:bg-red-900/30"
                  >
                    Delete
                  </button>
                </div>
              </div>
              {p.cutout_path && (
                <div className="mt-2 text-xs text-emerald-400">
                  Cutout ready: {p.cutout_path.split("/").pop()}
                </div>
              )}
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

export default ProductCatalog;