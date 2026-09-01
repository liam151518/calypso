import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

export interface SuggestionCardProps {
  suggestion: {
    id?: number;
    template_id: number | null;
    layer_overrides: Record<string, unknown>;
    rationale: string;
    platforms: string[];
    duration_s?: number | null;
    cost_usd: number;
    confidence_score: number;
  };
  previewUrl?: string | null;
  onAccept: (s: SuggestionCardProps["suggestion"]) => void;
  onSchedule: (s: SuggestionCardProps["suggestion"]) => void;
  onReject: (s: SuggestionCardProps["suggestion"]) => void;
  busy?: boolean;
}

export function SuggestionCard({
  suggestion,
  previewUrl,
  onAccept,
  onSchedule,
  onReject,
  busy,
}: SuggestionCardProps) {
  const hasTemplate = suggestion.template_id !== null;
  const confidencePct = Math.round(suggestion.confidence_score * 100);
  return (
    <Card className="overflow-hidden">
      <div className="aspect-square bg-slate-100 flex items-center justify-center overflow-hidden">
        {previewUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={previewUrl}
            alt="Suggestion preview"
            className="w-full h-full object-cover"
          />
        ) : (
          <div className="text-slate-400 text-sm p-6 text-center">
            {hasTemplate
              ? `Template #${suggestion.template_id} preview`
              : "No template available"}
          </div>
        )}
      </div>
      <CardContent className="space-y-3 p-4">
        <div>
          <div className="flex items-center justify-between text-xs text-slate-500">
            <span>Confidence</span>
            <span>{confidencePct}%</span>
          </div>
          <div className="h-1.5 w-full bg-slate-100 rounded-full overflow-hidden mt-1">
            <div
              className="h-full bg-slate-900"
              style={{ width: `${confidencePct}%` }}
            />
          </div>
        </div>
        <p className="text-sm text-slate-700 leading-snug">
          {suggestion.rationale}
        </p>
        <div className="flex flex-wrap gap-1 text-xs text-slate-500">
          <span>${suggestion.cost_usd.toFixed(2)}</span>
          {suggestion.platforms.length > 0 && (
            <span>· {suggestion.platforms.join(", ")}</span>
          )}
          {suggestion.duration_s != null && (
            <span>· {suggestion.duration_s}s</span>
          )}
        </div>
        <div className="grid grid-cols-3 gap-2 pt-2">
          <Button
            variant="default"
            size="sm"
            disabled={!hasTemplate || busy}
            onClick={() => onAccept(suggestion)}
          >
            Edit
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={!hasTemplate || busy}
            onClick={() => onSchedule(suggestion)}
          >
            Schedule
          </Button>
          <Button
            variant="ghost"
            size="sm"
            disabled={busy}
            onClick={() => onReject(suggestion)}
          >
            Reject
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

export default SuggestionCard;