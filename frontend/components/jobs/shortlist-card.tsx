import { AlertTriangle, CheckCircle2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { ScoreRing } from "@/components/ui/score-ring";
import type { ShortlistEntry } from "@/types/application";

export function ShortlistCard({ entry, rank }: { entry: ShortlistEntry; rank: number }) {
  return (
    <Card>
      <div className="flex items-start gap-4">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-surface text-xs font-semibold text-muted-foreground">
          #{rank}
        </div>

        <ScoreRing score={entry.match_score} size={56} label="match" />

        <div className="min-w-0 flex-1">
          <div className="mb-1 flex items-center justify-between gap-2">
            <h4 className="truncate text-sm font-semibold text-foreground">{entry.candidate_name}</h4>
            {entry.passed_guardrails ? (
              <Badge variant="success" className="shrink-0">
                <CheckCircle2 className="h-3 w-3" />
                Cleared
              </Badge>
            ) : (
              <Badge variant="warning" className="shrink-0">
                <AlertTriangle className="h-3 w-3" />
                Needs review
              </Badge>
            )}
          </div>

          <p className="mb-2 text-xs text-muted-foreground">{entry.recommendation}</p>

          {entry.top_skills.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {entry.top_skills.map((skill) => (
                <Badge key={skill} variant="default">
                  {skill}
                </Badge>
              ))}
            </div>
          )}

          {!entry.passed_guardrails && entry.bias_flags.length > 0 && (
            <p className="mt-2 text-xs text-warning">Flagged: {entry.bias_flags.join(", ")}</p>
          )}
        </div>
      </div>
    </Card>
  );
}
