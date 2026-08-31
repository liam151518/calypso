import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import {
  Clapperboard,
  Cog,
  Library,
  Palette,
  Search,
  Sparkles,
} from "lucide-react";
import { useEffect } from "react";

import { BrandMark } from "./BrandMark";
import { Button } from "@/components/ui/button";
import { TooltipProvider } from "@/components/ui/tooltip";
import { useHealth } from "@/lib/query";
import { cn } from "@/lib/utils";

const NAV = [
  { to: "/generate", label: "Generate", icon: Sparkles, hint: "G" },
  { to: "/outputs", label: "Outputs", icon: Clapperboard, hint: "O" },
  { to: "/references", label: "References", icon: Library, hint: "R" },
  { to: "/brand", label: "Brand", icon: Palette, hint: "B" },
  { to: "/settings", label: "Settings", icon: Cog, hint: "S" },
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
      <nav className="flex-1 px-2 py-3" aria-label="Primary">
        <ul className="flex flex-col gap-0.5">
          {NAV.map((item) => (
            <li key={item.to}>
              <NavLink
                to={item.to}
                data-testid={`nav-${item.label.toLowerCase()}`}
                className={({ isActive }) =>
                  cn(
                    "group relative flex items-center gap-3 rounded-md px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground",
                    isActive && "text-foreground",
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
