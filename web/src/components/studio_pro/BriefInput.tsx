import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Wand2 } from "lucide-react";
import { useState } from "react";

export interface BriefInputProps {
  onSubmit: (brief: {
    brief: string;
    product_id: number | null;
    brand_id: number | null;
    platforms: string[];
    budget_usd: number;
    audience?: string | null;
    duration_s?: number | null;
  }) => void;
  isLoading?: boolean;
  brandId?: number | null;
  productId?: number | null;
}

const DEFAULT_PLATFORMS = ["instagram", "tiktok", "linkedin", "youtube"];

export function BriefInput({
  onSubmit,
  isLoading,
  brandId,
  productId,
}: BriefInputProps) {
  const [brief, setBrief] = useState("");
  const [budget, setBudget] = useState(5.0);
  const [platforms, setPlatforms] = useState<string[]>(["instagram"]);
  const [audience, setAudience] = useState("");
  const [duration, setDuration] = useState<number | null>(null);

  const submit = () => {
    if (!brief.trim() || isLoading) return;
    onSubmit({
      brief: brief.trim(),
      product_id: productId ?? null,
      brand_id: brandId ?? null,
      platforms,
      budget_usd: budget,
      audience: audience.trim() || null,
      duration_s: duration,
    });
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-lg">
          <Wand2 className="h-5 w-5" />
          Studio Pro — brief
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-1">
          <Label htmlFor="brief">Creative brief</Label>
          <Textarea
            id="brief"
            placeholder="Make a 30s unboxing for these new sneakers, hype energy, 18-25 streetwear"
            value={brief}
            onChange={(e) => setBrief(e.target.value)}
            rows={4}
            disabled={isLoading}
          />
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-1">
            <Label htmlFor="budget">Budget (USD)</Label>
            <Input
              id="budget"
              type="number"
              min={0}
              step={0.5}
              value={budget}
              onChange={(e) => setBudget(parseFloat(e.target.value) || 0)}
              disabled={isLoading}
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor="duration">Duration (s)</Label>
            <Input
              id="duration"
              type="number"
              min={1}
              max={120}
              value={duration ?? ""}
              onChange={(e) =>
                setDuration(e.target.value ? parseInt(e.target.value, 10) : null)
              }
              disabled={isLoading}
            />
          </div>
        </div>
        <div className="space-y-1">
          <Label htmlFor="audience">Audience (optional)</Label>
          <Input
            id="audience"
            placeholder="18-25 streetwear"
            value={audience}
            onChange={(e) => setAudience(e.target.value)}
            disabled={isLoading}
          />
        </div>
        <div className="space-y-1">
          <Label>Platforms</Label>
          <div className="flex flex-wrap gap-2">
            {DEFAULT_PLATFORMS.map((p) => {
              const on = platforms.includes(p);
              return (
                <button
                  key={p}
                  type="button"
                  onClick={() =>
                    setPlatforms((cur) =>
                      on ? cur.filter((x) => x !== p) : [...cur, p]
                    )
                  }
                  disabled={isLoading}
                  className={`rounded-full border px-3 py-1 text-xs ${
                    on
                      ? "bg-slate-900 text-white border-slate-900"
                      : "bg-white text-slate-700 border-slate-300"
                  }`}
                >
                  {p}
                </button>
              );
            })}
          </div>
        </div>
        <Button
          onClick={submit}
          disabled={!brief.trim() || isLoading}
          className="w-full"
        >
          {isLoading ? "Generating…" : "Generate suggestions"}
        </Button>
      </CardContent>
    </Card>
  );
}

export default BriefInput;