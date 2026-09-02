import { lazy, Suspense } from "react";
import { Route, Routes } from "react-router-dom";
import { AppShell } from "@/components/layout/AppShell";
import { CommandPalette } from "@/components/layout/CommandPalette";
import { LoadingSkeleton } from "@/components/layout/LoadingSkeleton";
import { GeneratePage } from "@/pages/Generate";
import { ImagePage } from "@/pages/Image";
import { OutputsPage } from "@/pages/Outputs";
import { ReferencesPage } from "@/pages/References";
import { BrandPage } from "@/pages/Brand";
import { SettingsPage } from "@/pages/Settings";

// Heavy routes are split into their own chunks so the initial bundle stays
// small. Each lazy import gets a thin Suspense wrapper.
const PipelineList = lazy(() => import("@/pages/PipelineList").then((m) => ({ default: m.PipelineList })));
const PipelinePage = lazy(() => import("@/pages/Pipeline").then((m) => ({ default: m.PipelinePage })));
const StudioPage = lazy(() => import("@/pages/Studio").then((m) => ({ default: m.StudioPage })));
const ExtensionsPage = lazy(() => import("@/pages/Extensions").then((m) => ({ default: m.ExtensionsPage })));
const MarketingPage = lazy(() => import("@/pages/Marketing").then((m) => ({ default: m.MarketingPage })));
const TemplateGallery = lazy(() => import("@/pages/TemplateGallery").then((m) => ({ default: m.TemplateGallery })));
const ProductCatalog = lazy(() => import("@/pages/ProductCatalog").then((m) => ({ default: m.ProductCatalog })));
const EditorPage = lazy(() => import("@/pages/Editor").then((m) => ({ default: m.EditorPage })));
const FeedPreview = lazy(() => import("@/pages/FeedPreview").then((m) => ({ default: m.FeedPreview })));
const StudioPro = lazy(() => import("@/pages/StudioPro").then((m) => ({ default: m.StudioPro })));
const PresetManager = lazy(() => import("@/pages/PresetManager").then((m) => ({ default: m.PresetManager })));
const AutomationRules = lazy(() => import("@/pages/AutomationRules").then((m) => ({ default: m.AutomationRules })));
const RefinementPage = lazy(() => import("@/pages/Refinement").then((m) => ({ default: m.RefinementPage })));
const SkillsPage = lazy(() => import("@/pages/Skills").then((m) => ({ default: m.SkillsPage })));
const NotFoundPage = lazy(() => import("@/pages/NotFound").then((m) => ({ default: m.NotFoundPage })));

function PageFallback() {
  return (
    <div className="flex flex-col gap-6 p-6">
      <LoadingSkeleton rows={6} />
    </div>
  );
}

export default function App() {
  return (
    <>
      <Suspense fallback={<PageFallback />}>
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
            <Route path="/refine/:outputId" element={<RefinementPage />} />
            <Route path="/skills" element={<SkillsPage />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="*" element={<NotFoundPage />} />
          </Route>
        </Routes>
      </Suspense>
      <CommandPalette />
    </>
  );
}
