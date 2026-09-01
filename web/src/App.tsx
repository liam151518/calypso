import { Route, Routes } from "react-router-dom";
import { AppShell } from "@/components/layout/AppShell";
import { CommandPalette } from "@/components/layout/CommandPalette";
import { GeneratePage } from "@/pages/Generate";
import { ImagePage } from "@/pages/Image";
import { OutputsPage } from "@/pages/Outputs";
import { ReferencesPage } from "@/pages/References";
import { BrandPage } from "@/pages/Brand";
import { SettingsPage } from "@/pages/Settings";
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
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
      <CommandPalette />
    </>
  );
}
