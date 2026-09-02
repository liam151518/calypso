import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import {
  Boxes,
  Calendar,
  Clapperboard,
  ImagePlus,
  Layers,
  Library,
  Package,
  Palette,
  Plug,
  Search,
  Settings2,
  Sparkles,
  Wand2,
  Workflow,
  Zap,
} from "lucide-react";
import { useEffect } from "react";

import { BrandMark } from "./BrandMark";
import { Button } from "@/components/ui/button";
import { TooltipProvider } from "@/components/ui/tooltip";
import { useHealth } from "@/lib/query";
import { cn } from "@/lib/utils";

type NavItem = {
  to: string;
  label: string;
  icon: typeof Sparkles;
  hint: string;
};

type NavSection = {
  title: string;
  items: NavItem[];
};

// Logical groupings of the surface area. The labels reflect how an
// operator thinks about the product, not how the codebase is split.
const NAV_SECTIONS: NavSection[] = [
  {
    title: "Create",
    items: [
      { to: "/generate", label: "Generate", icon: Sparkles, hint: "G" },
      { to: "/image", label: "Image", icon: ImagePlus, hint: "I" },
      { to: "/studio", label: "Studio", icon: Wand2, hint: "S" },
      { to: "/studio-pro", label: "Studio Pro", icon: Boxes, hint: "P" },
      { to: "/pipelines", label: "Pipelines", icon: Workflow, hint: "W" },
    ],
  },
  {
    title: "Library",
    items: [
      { to: "/outputs", label: "Outputs", icon: Clapperboard, hint: "O" },
      { to: "/references", label: "References", icon: Library, hint: "R" },
      { to: "/templates", label: "Templates", icon: Layers, hint: "T" },
      { to: "/products", label: "Products", icon: Package, hint: "D" },
      { to: "/brand", label: "Brand", icon: Palette, hint: "B" },
    ],
  },
  {
    title: "Workflow",
    items: [
      { to: "/presets", label: "Presets", icon: Layers, hint: "X" },
      { to: "/automation", label: "Automation", icon: Zap, hint: "A" },
      { to: "/marketing", label: "Marketing", icon: Calendar, hint: "M" },
    ],
  },
  {
    title: "Extend",
    items: [
      { to: "/skills", label: "Skills", icon: Sparkles, hint: "K" },
      { to: "/extensions", label: "Extensions", icon: Plug, hint: "E" },
    ],
  },
  {
    title: "System",
    items: [
      { to: "/settings", label: "Settings", icon: Settings2, hint: "S" },
    ],
  },
];

export function AppShell() {
  return (
    <TooltipProvider delayDuration={250}>
      <ShellInner />
    </TooltipProvider>
  );
}

function ShellInner() {
  const { data: health } = useHealth();
  const location = useLocation();

  // Cmd+K opens the palette via a custom event so CommandPalette can listen.
  // (Declared as a global event so the palette can register itself once.)
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        window.dispatchEvent(new CustomEvent("calypso:open-command"));
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const isOnline = health?.status === "ok";

  return (
    <div className="flex min-h-screen w-full bg-background text-foreground">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar online={!!isOnline} path={location.pathname} />
        <main
          data-testid="page-outlet"
          className="mx-auto w-full max-w-6xl flex-1 px-6 py-8"
        >
          <Outlet />
        </main>
      </div>
    </div>
  );
}

function Sidebar() {
  return (
    <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col border-r border-border bg-card/40 md:flex">
      <div className="flex items-center gap-2.5 border-b border-border px-4 py-4">
        <BrandMark />
        <div className="flex flex-col">
          <span className="text-sm font-semibold tracking-tight">Calypso</span>
          <span className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
            Operator
          </span>
        </div>
      </div>
      <nav
        className="flex-1 overflow-y-auto px-2 py-3"
        aria-label="Primary"
      >
        <ul className="flex flex-col gap-4">
          {NAV_SECTIONS.map((section) => (
            <li key={section.title}>
              <div className="flex items-center gap-2 px-3 pb-1.5 pt-1">
                <span className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                  {section.title}
                </span>
                <span
                  aria-hidden="true"
                  className="h-px flex-1 bg-border/60"
                />
                <span className="text-[10px] font-mono text-muted-foreground/70">
                  {section.items.length}
                </span>
              </div>
              <ul className="flex flex-col gap-0.5">
                {section.items.map((item) => (
                  <li key={item.to}>
                    <NavLink
                      to={item.to}
                      data-testid={`nav-${item.label.toLowerCase()}`}
                      className={({ isActive }) =>
                        cn(
                          "group relative flex items-center gap-3 rounded-md px-3 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground",
                          isActive && "bg-accent text-foreground",
                        )
                      }
                    >
                      {({ isActive }) => (
                        <>
                          <span
                            aria-hidden="true"
                            className={cn(
                              "absolute inset-y-1 left-0 w-0.5 rounded-full bg-primary transition-opacity",
                              isActive ? "opacity-100" : "opacity-0",
                            )}
                          />
                          <item.icon className="h-4 w-4" />
                          <span className="flex-1">{item.label}</span>
                          <kbd className="hidden rounded border border-border bg-secondary px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground group-hover:inline">
                            {item.hint}
                          </kbd>
                        </>
                      )}
                    </NavLink>
                  </li>
                ))}
              </ul>
            </li>
          ))}
        </ul>
      </nav>
      <div className="border-t border-border p-3">
        <Button
          variant="outline"
          size="sm"
          className="w-full justify-start gap-2"
          onClick={() =>
            window.dispatchEvent(new CustomEvent("calypso:open-command"))
          }
        >
          <Search className="h-4 w-4" />
          Command
          <kbd className="ml-auto rounded border border-border bg-secondary px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">
            ⌘K
          </kbd>
        </Button>
        <Link
          to="/settings"
          className="mt-2 flex items-center justify-between rounded-md px-2 py-1.5 text-[11px] text-muted-foreground hover:text-foreground"
        >
          <span>v0.1.0</span>
          <span className="font-mono uppercase tracking-wide">local</span>
        </Link>
      </div>
    </aside>
  );
}

function TopBar({ online, path }: { online: boolean; path: string }) {
  const crumb = path === "/" ? "Generate" : (path.split("/")[1] || "Generate");
  return (
    <header className="sticky top-0 z-30 flex h-12 items-center justify-between border-b border-border bg-background/85 px-6 backdrop-blur">
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <span className="font-mono uppercase tracking-wide">Calypso</span>
        <span aria-hidden="true">/</span>
        <span className="text-foreground">{titleCase(crumb)}</span>
      </div>
      <div className="flex items-center gap-2 text-xs">
        <span
          className={cn(
            "inline-flex items-center gap-1.5 rounded-full border border-border px-2 py-0.5",
            online ? "text-ok" : "text-muted-foreground",
          )}
        >
          <span
            aria-hidden="true"
            className={cn(
              "h-1.5 w-1.5 rounded-full",
              online ? "bg-ok" : "bg-muted-foreground",
            )}
          />
          {online ? "Online" : "Offline"}
        </span>
      </div>
    </header>
  );
}

function titleCase(s: string) {
  return s.length ? s[0].toUpperCase() + s.slice(1) : s;
}
