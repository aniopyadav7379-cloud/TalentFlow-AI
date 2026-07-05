"use client";

import { Bot, CheckCircle2, XCircle } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ErrorAlert } from "@/components/ui/feedback";
import { mastraApi, MastraError, type HiringWorkflowTriggerResult } from "@/lib/mastra-client";
import type { Job } from "@/types/job";

/**
 * Demonstrates the Mastra-orchestrated hiring workflow: candidate ranking ->
 * guardrail check -> human-in-the-loop approval -> recommendation. This is
 * a SEPARATE path from the "Run AI Shortlist" button above — that button
 * still calls the backend's own ShortlistPipeline directly, unchanged.
 * This panel exists to demo/exercise the new mastra/ orchestration layer
 * specifically, with its explicit approval gate.
 */
export function MastraAgentPanel({ job }: { job: Job }) {
  const [state, setState] = useState<HiringWorkflowTriggerResult | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function trigger() {
    setError(null);
    setIsLoading(true);
    try {
      const result = await mastraApi.triggerHiringWorkflow({
        recruiterId: "demo-recruiter", // in a full build this would be the logged-in user's id
        jobTitle: job.title,
        jobDescription: job.description,
        jobSkills: job.skills,
        topK: 10,
      });
      setState(result);
    } catch (err) {
      setError(err instanceof MastraError ? err.message : "Couldn't reach the Mastra service.");
    } finally {
      setIsLoading(false);
    }
  }

  async function respond(approved: boolean) {
    if (!state) return;
    setError(null);
    setIsLoading(true);
    try {
      const result = await mastraApi.approveHiringWorkflow(state.runId, approved, "Recruiter");
      setState(result);
    } catch (err) {
      setError(err instanceof MastraError ? err.message : "Couldn't reach the Mastra service.");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <Card className="mt-6">
      <div className="mb-3 flex items-center gap-2">
        <Bot className="h-4 w-4 text-accent" />
        <h3 className="text-sm font-semibold text-foreground">Run via Mastra Agent</h3>
        <Badge variant="accent">orchestration demo</Badge>
      </div>
      <p className="mb-4 text-xs text-muted-foreground">
        Runs the same ranking + guardrail + recommendation pipeline through the Mastra orchestration layer
        (mastra/), with an explicit human-approval step before any recommendation is generated. Requires the
        Mastra service running separately — see mastra/README.md.
      </p>

      {error && (
        <div className="mb-3">
          <ErrorAlert message={error} />
        </div>
      )}

      {!state && (
        <Button variant="secondary" onClick={trigger} isLoading={isLoading}>
          Trigger hiring workflow
        </Button>
      )}

      {state?.status === "suspended" && state.approvalNeeded && (
        <div className="space-y-3">
          <div className="rounded-lg border border-border bg-surface p-3 text-sm">
            <p className="text-foreground">
              Top candidate match score: <span className="font-semibold">{state.approvalNeeded.matchScore ?? "—"}</span>
            </p>
            <p className="mt-1 text-xs text-muted-foreground">{state.approvalNeeded.reason}</p>
            {!state.approvalNeeded.guardrailsPassed && (
              <p className="mt-1 text-xs text-warning">Guardrail flags: {state.approvalNeeded.biasFlags.join(", ")}</p>
            )}
          </div>
          <div className="flex gap-2">
            <Button onClick={() => respond(true)} isLoading={isLoading}>
              <CheckCircle2 className="h-4 w-4" />
              Approve
            </Button>
            <Button variant="destructive" onClick={() => respond(false)} isLoading={isLoading}>
              <XCircle className="h-4 w-4" />
              Reject
            </Button>
          </div>
        </div>
      )}

      {state?.status === "success" && state.result && (
        <div className="rounded-lg border border-border bg-surface p-3 text-sm">
          <p className="font-semibold text-foreground">{state.result.decision.replace("_", " ")}</p>
          <p className="mt-1 text-xs text-muted-foreground">{state.result.summary}</p>
        </div>
      )}

      {state?.status === "failed" && (
        <ErrorAlert message="The workflow failed — likely no OPENAI_API_KEY configured on the Mastra/backend side. Check mastra/README.md." />
      )}
    </Card>
  );
}
