import { Route, Routes } from "react-router-dom";
import { AppShell } from "@/components/layout/AppShell";
import { CommandPalette } from "@/components/layout/CommandPalette";
import { GeneratePage } from "@/pages/Generate";
import { ImagePage } from "@/pages/Image";
import { OutputsPage } from "@/pages/Outputs";
import { ReferencesPage } from "@/pages/References";
import { BrandPage } from "@/pages/Brand";
import { SettingsPage } from "@/pages/Settings";
import { PipelineList } from "@/pages/PipelineList";
import { PipelinePage } from "@/pages/Pipeline";
import { StudioPage } from "@/pages/Studio";
import { ExtensionsPage } from "@/pages/Extensions";
import { MarketingPage } from "@/pages/Marketing";
import { TemplateGallery } from "@/pages/TemplateGallery";
import { ProductCatalog } from "@/pages/ProductCatalog";
import { EditorPage } from "@/pages/Editor";
import { FeedPreview } from "@/pages/FeedPreview";
import { StudioPro } from "@/pages/StudioPro";
import { PresetManager } from "@/pages/PresetManager";
import { AutomationRules } from "@/pages/AutomationRules";
import { NotFoundPage } from "@/pages/NotFound";

export default function App() {
  return (
    <>
      <Routes>
        <Route element={<AppShell />}>
          <Route index element={<GeneratePage />} />
          <Route path="/generate" element={<GeneratePage />} />
          <Route path="/image" element={<ImagePage />} />
          <Route path="/outputs" element={<OutputsPage />} />
          <Route path="/references" element={<ReferencesPage />} />
          <Route path="/brand" element={<BrandPage />} />
          <Route path="/pipelines" element={<PipelineList />} />
          <Route path="/pipelines/:id" element={<PipelinePage />} />
          <Route path="/studio" element={<StudioPage />} />
          <Route path="/extensions" element={<ExtensionsPage />} />
          <Route path="/marketing" element={<MarketingPage />} />
          <Route path="/templates" element={<TemplateGallery />} />
          <Route path="/products" element={<ProductCatalog />} />
          <Route path="/editor/:templateId" element={<EditorPage />} />
          <Route path="/editor" element={<EditorPage />} />
          <Route path="/feed" element={<FeedPreview />} />
          <Route path="/studio-pro" element={<StudioPro />} />
          <Route path="/presets" element={<PresetManager />} />
          <Route path="/automation" element={<AutomationRules />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
      <CommandPalette />
    </>
  );
}
