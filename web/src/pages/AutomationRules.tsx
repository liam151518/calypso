import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import {
  AutomationRule,
  useAutomationRules,
  useCreateAutomationRule,
  useDeleteAutomationRule,
  useToggleAutomationRule,
} from "@/hooks/presets";


const TRIGGERS = ["product_added", "product_updated", "campaign_scheduled"];
const ACTION_KINDS = ["apply_preset", "schedule_caption"];

export interface AutomationRulesProps {
  brandId?: number | null;
}

export function AutomationRules({ brandId }: AutomationRulesProps) {
  const rulesQ = useAutomationRules(brandId);
  const create = useCreateAutomationRule();
  const del = useDeleteAutomationRule();
  const toggle = useToggleAutomationRule();

  const [name, setName] = useState("");
  const [trigger, setTrigger] = useState(TRIGGERS[0]);
  const [actionKind, setActionKind] = useState(ACTION_KINDS[0]);
  const [presetId, setPresetId] = useState("");
  const [conditionJson, setConditionJson] = useState("[]");

  const submit = () => {
    if (!name.trim()) return;
    let conditions: AutomationRule["conditions"] = [];
    try {
      conditions = JSON.parse(conditionJson || "[]");
    } catch {
      alert("Conditions must be a JSON array of {field, op, value} objects.");
      return;
    }
    const action: AutomationRule["action"] =
      actionKind === "apply_preset"
        ? {
            kind: "apply_preset",
            preset_id: presetId ? parseInt(presetId, 10) : null,
          }
        : { kind: "schedule_caption" };
    create.mutate({
      brand_id: brandId ?? null,
      name: name.trim(),
      trigger,
      conditions,
      action,
    });
    setName("");
    setPresetId("");
    setConditionJson("[]");
  };

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-semibold">Automation rules</h1>
        <p className="text-sm text-slate-500">
          When X happens, run Y. Use JSON conditions like
          <code className="mx-1 rounded bg-slate-100 px-1">
            {"[{\"field\": \"category\", \"op\": \"eq\", \"value\": \"shoes\"}]"}
          </code>
          .
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">New rule</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label htmlFor="r-name">Name</Label>
              <Input
                id="r-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Auto-sneaker-drop"
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="r-trigger">Trigger</Label>
              <select
                id="r-trigger"
                value={trigger}
                onChange={(e) => setTrigger(e.target.value)}
                className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              >
                {TRIGGERS.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label htmlFor="r-action">Action</Label>
              <select
                id="r-action"
                value={actionKind}
                onChange={(e) => setActionKind(e.target.value)}
                className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              >
                {ACTION_KINDS.map((k) => (
                  <option key={k} value={k}>
                    {k}
                  </option>
                ))}
              </select>
            </div>
            {actionKind === "apply_preset" && (
              <div className="space-y-1">
                <Label htmlFor="r-preset">Preset ID</Label>
                <Input
                  id="r-preset"
                  value={presetId}
                  onChange={(e) => setPresetId(e.target.value)}
                  placeholder="e.g. 1"
                />
              </div>
            )}
          </div>
          <div className="space-y-1">
            <Label htmlFor="r-cond">Conditions (JSON array)</Label>
            <textarea
              id="r-cond"
              className="min-h-[80px] w-full rounded-md border border-slate-300 px-3 py-2 text-sm font-mono"
              value={conditionJson}
              onChange={(e) => setConditionJson(e.target.value)}
            />
          </div>
          <Button
            onClick={submit}
            disabled={!name.trim() || create.isPending}
          >
            <Plus className="mr-2 h-4 w-4" />
            Save rule
          </Button>
        </CardContent>
      </Card>

      <div>
        <h2 className="text-sm font-medium uppercase tracking-wide text-slate-500 mb-2">
          Active rules ({rulesQ.data?.rules?.length ?? 0})
        </h2>
        {rulesQ.data?.rules?.length ? (
          <ul className="space-y-2">
            {rulesQ.data.rules.map((r: AutomationRule) => (
              <li
                key={r.id}
                className="flex items-start justify-between rounded-md border border-slate-200 bg-white p-3"
              >
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{r.name}</span>
                    <span
                      className={`text-xs uppercase ${
                        r.is_active ? "text-green-600" : "text-slate-400"
                      }`}
                    >
                      {r.is_active ? "active" : "inactive"}
                    </span>
                  </div>
                  <div className="mt-1 text-xs text-slate-500">
                    trigger <code>{r.trigger}</code> · action{" "}
                    <code>{String(r.action.kind)}</code>
                  </div>
                  <div className="mt-1 text-xs text-slate-400">
                    {r.conditions.length} condition
                    {r.conditions.length === 1 ? "" : "s"}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() =>
                      toggle.mutate({
                        rule_id: r.id,
                        is_active: !r.is_active,
                      })
                    }
                  >
                    {r.is_active ? "Disable" : "Enable"}
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => del.mutate(r.id)}
                    aria-label={`Delete ${r.name}`}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <div className="rounded-md border border-dashed border-slate-300 p-6 text-center text-sm text-slate-500">
            No automation rules yet.
          </div>
        )}
      </div>
    </div>
  );
}

export default AutomationRules;