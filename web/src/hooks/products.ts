// Re-export the products hooks from the templates module so editors
// importing from `web/src/hooks/products` can colocate their imports.
export {
  useProducts,
  useProduct,
  useCreateProduct,
  useDeleteProduct,
  useImportProducts,
  useCutout,
} from "./templates";