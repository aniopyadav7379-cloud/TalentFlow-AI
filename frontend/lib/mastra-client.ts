/**
 * Client for the Mastra orchestration service (mastra/), separate from
 * lib/api-client.ts which talks to the FastAPI backend directly. Additive
 * only — the existing "Run AI Shortlist" button and its api-client.ts call
 * are untouched; this powers a new, clearly-labeled "Run via Mastra Agent"
 * path so the orchestrated, human-in-the-loop flow can be demoed
 * alongside the existing direct pipeline, not instead of it.
 */
import { getToken } from "@/lib/auth-storage";

const MASTRA_BASE_URL = process.env.NEXT_PUBLIC_MASTRA_BASE_URL ?? "http://localhost:4111";

export class MastraError extends Error {}

async function mastraRequest<T>(path: string, body: unknown): Promise<T> {
  const token = getToken();
  if (!token) throw new MastraError("Not authenticated");

  const response = await fetch(`${MASTRA_BASE_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const errorBody = await response.json();
      detail = errorBody.error ?? errorBody.detail ?? detail;
    } catch {
      // fall back to statusText
    }
    throw new MastraError(detail);
  }
  return response.json() as Promise<T>;
}

export interface HiringWorkflowTriggerResult {
  runId: string;
  status: "suspended" | "success" | "failed";
  suspendedStep?: string[];
  approvalNeeded?: {
    topCandidateId: string | null;
    matchScore: number | null;
    guardrailsPassed: boolean;
    biasFlags: string[];
    reason: string;
  };
  result?: {
    candidateId: string | null;
    questions: Array<{ id: string; question: string; category: string }>;
    decision: string;
    summary: string;
    rationale: string;
  };
}

export const mastraApi = {
  triggerHiringWorkflow: (payload: {
    recruiterId: string;
    jobTitle: string;
    jobDescription?: string;
    jobSkills?: string[];
    topK?: number;
  }) => mastraRequest<HiringWorkflowTriggerResult>("/workflows/hiring/trigger", payload),

  approveHiringWorkflow: (runId: string, approved: boolean, approverName?: string) =>
    mastraRequest<HiringWorkflowTriggerResult>(`/workflows/hiring/${runId}/approve`, { approved, approverName }),
};
