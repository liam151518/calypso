import { useMemo, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Cog,
  KeyRound,
  Plus,
  ShieldCheck,
} from "lucide-react";

import { PageHeader } from "@/components/layout/PageHeader";
import { KeyRow } from "@/components/domain/KeyRow";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { LoadingSkeleton } from "@/components/layout/LoadingSkeleton";
import {
  useKeys,
  useSetKey,
  useTestKey,
} from "@/lib/query";
import { toast as sonnerToast } from "sonner";

export function SettingsPage() {
  const keys = useKeys();
  const set = useSetKey();
  const test = useTestKey();

  const grouped = useMemo(() => {
    const preset = keys.data?.keys ?? [];
    const custom = keys.data?.custom ?? [];
    const groups = keys.data?.groups ?? [];

    const groupedPreset = groups.map((g) => ({
      name: g.name,
      items: preset.filter((k) => g.keys.includes(k.env_var)),
    }));
    const requiredTotal = preset.filter((k) => k.required).length;
    const requiredSet = preset.filter((k) => k.required && k.is_set).length;
    return { groupedPreset, custom, preset, requiredTotal, requiredSet };
  }, [keys.data]);

  const [customName, setCustomName] = useState("");
  const [customValue, setCustomValue] = useState("");
  const [customShow, setCustomShow] = useState(false);

  function handleAddCustom() {
    const env_var = customName.trim().toUpperCase().replace(/[^A-Z0-9_]/g, "_");
    if (!env_var) {
      sonnerToast.error("Enter a name for the key.");
      return;
    }
    if (!customValue.trim()) {
      sonnerToast.error("Paste a value first.");
      return;
    }
    set.mutate(
      { env_var, value: customValue.trim() },
      {
        onSuccess: () => {
          sonnerToast.success(`Saved ${env_var}`);
          setCustomName("");
          setCustomValue("");
          setCustomShow(false);
        },
        onError: (err) =>
          sonnerToast.error(
            err instanceof Error ? err.message : "Save failed",
          ),
      },
    );
  }

  function handleTest(env_var: string) {
    test.mutate(env_var, {
      onSuccess: () => sonnerToast.success(`${env_var} looks good.`),
      onError: (err) =>
        sonnerToast.error(
          err instanceof Error ? err.message : "Test failed",
        ),
    });
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        meta="Operator · Settings"
        title="API keys & connections"
        description="Everything you need to plug Calypso into your accounts. Paste a key here once and it lives in your local .env file — never uploaded anywhere."
      />

      {/* Status banner */}
      {!keys.isLoading && grouped.preset.length > 0 && (
        <Card>
          <CardContent className="flex items-center justify-between gap-3 p-4">
            <div className="flex items-center gap-3">
              {grouped.requiredTotal === grouped.requiredSet ? (
                <ShieldCheck className="h-5 w-5 text-emerald-500" />
              ) : (
                <AlertTriangle className="h-5 w-5 text-amber-500" />
              )}
              <div className="flex flex-col">
                <span className="text-sm font-medium">
                  {grouped.requiredTotal === grouped.requiredSet
                    ? "All required keys are set."
                    : `${grouped.requiredSet} of ${grouped.requiredTotal} required keys configured.`}
                </span>
                <span className="text-xs text-muted-foreground">
                  {grouped.preset.filter((k) => k.is_set).length} of{" "}
                  {grouped.preset.length} known keys are set.
                  {grouped.custom.length > 0
                    ? ` ${grouped.custom.length} custom key${grouped.custom.length === 1 ? "" : "s"} also stored.`
                    : ""}
                </span>
              </div>
            </div>
            <Badge variant="muted" className="gap-1 font-mono">
              <Cog className="h-3 w-3" /> .env
            </Badge>
          </CardContent>
        </Card>
      )}

      {keys.isLoading ? (
        <LoadingSkeleton rows={6} />
      ) : (
        <div className="flex flex-col gap-6">
          {grouped.groupedPreset.map((group) => (
            <section key={group.name} className="flex flex-col gap-3">
              <div className="flex items-center gap-2">
                <h2 className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                  {group.name}
                </h2>
                <span className="text-[11px] text-muted-foreground">
                  · {group.items.filter((k) => k.is_set).length}/
                  {group.items.length} set
                </span>
              </div>
              <Card>
                <CardContent className="flex flex-col gap-3 p-4">
                  {group.items.map((k) => (
                    <KeyRow
                      key={k.env_var}
                      k={k}
                      onTest={() => handleTest(k.env_var)}
                      testing={test.isPending && test.variables === k.env_var}
                    />
                  ))}
                </CardContent>
              </Card>
            </section>
          ))}

          {grouped.custom.length > 0 && (
            <section className="flex flex-col gap-3">
              <h2 className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                Custom keys
              </h2>
              <Card>
                <CardContent className="flex flex-col gap-3 p-4">
                  {grouped.custom.map((k) => (
                    <KeyRow
                      key={k.env_var}
                      k={k}
                      onTest={() => handleTest(k.env_var)}
                      testing={
                        test.isPending && test.variables === k.env_var
                      }
                    />
                  ))}
                </CardContent>
              </Card>
            </section>
          )}

          {/* Add custom key */}
          <section className="flex flex-col gap-3">
            <h2 className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
              Add a custom key
            </h2>
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-sm">
                  <Plus className="h-4 w-4" /> Set any env var from the UI
                </CardTitle>
              </CardHeader>
              <CardContent className="flex flex-col gap-3">
                <p className="text-xs text-muted-foreground">
                  Useful if you wired up a custom integration or need to override
                  one of the preset keys. Names must be uppercase letters, digits,
                  and underscores (e.g. <code>MY_SERVICE_TOKEN</code>).
                </p>
                <div className="grid grid-cols-1 gap-3 md:grid-cols-[1fr_2fr_auto] md:items-end">
                  <div className="flex flex-col gap-1">
                    <Label htmlFor="custom-name">Key name</Label>
                    <Input
                      id="custom-name"
                      placeholder="MY_SERVICE_TOKEN"
                      value={customName}
                      onChange={(e) => setCustomName(e.target.value)}
                      autoComplete="off"
                      className="font-mono"
                    />
                  </div>
                  <div className="flex flex-col gap-1">
                    <Label htmlFor="custom-value">Value</Label>
                    <Input
                      id="custom-value"
                      type={customShow ? "text" : "password"}
                      placeholder="paste the secret here"
                      value={customValue}
                      onChange={(e) => setCustomValue(e.target.value)}
                      autoComplete="off"
                      className="font-mono"
                    />
                  </div>
                  <Button
                    onClick={handleAddCustom}
                    disabled={set.isPending || !customName.trim() || !customValue.trim()}
                  >
                    <KeyRound className="h-4 w-4" />
                    Save custom key
                  </Button>
                </div>
              </CardContent>
            </Card>
          </section>
        </div>
      )}

      <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
        <CheckCircle2 className="h-3 w-3" />
        Changes take effect on the next request. No restart required.
      </div>
    </div>
  );
}
