import { SuggestionCard, SuggestionCardProps } from "./SuggestionCard";

export interface SuggestionGridProps {
  suggestions: SuggestionCardProps["suggestion"][];
  previews?: Record<number, string | null>;
  onAccept: (s: SuggestionCardProps["suggestion"]) => void;
  onSchedule: (s: SuggestionCardProps["suggestion"]) => void;
  onReject: (s: SuggestionCardProps["suggestion"]) => void;
  busy?: boolean;
}

export function SuggestionGrid({
  suggestions,
  previews,
  onAccept,
  onSchedule,
  onReject,
  busy,
}: SuggestionGridProps) {
  if (!suggestions.length) {
    return (
      <div className="rounded-lg border border-dashed border-slate-300 p-8 text-center text-sm text-slate-500">
        Submit a brief to generate suggestions.
      </div>
    );
  }
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      {suggestions.map((s, idx) => (
        <SuggestionCard
          key={`${s.template_id ?? "none"}-${idx}`}
          suggestion={s}
          previewUrl={s.template_id ? previews?.[s.template_id] ?? null : null}
          onAccept={onAccept}
          onSchedule={onSchedule}
          onReject={onReject}
          busy={busy}
        />
      ))}
    </div>
  );
}

export default SuggestionGrid;