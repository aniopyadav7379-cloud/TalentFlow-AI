import { createTool } from "@mastra/core/tools";
import { z } from "zod";

import { backendClient } from "../services/backendClient.js";

export const recommendationTool = createTool({
  id: "get-recommendation",
  description:
    "Synthesize a final hiring recommendation from a candidate's match score and interview performance. Requires " +
    "guardrailsPassed/biasFlags from a prior enkryptTool call — if guardrails failed, the backend forces a 'hold' " +
    "decision regardless of how strong the scores look, in code, not just via prompt instruction.",
  inputSchema: z.object({
    candidateName: z.string(),
    matchScore: z.number().min(0).max(100),
    matchRationale: z.string().default(""),
    interviewOverallScore: z.number().nullable().optional(),
    interviewScoreBreakdown: z.record(z.string(), z.number()).nullable().optional(),
    guardrailsPassed: z.boolean(),
    biasFlags: z.array(z.string()).default([]),
    bearerToken: z.string(),
  }),
  outputSchema: z.object({
    decision: z.enum(["strong_hire", "hire", "hold", "no_hire"]),
    summary: z.string(),
    rationale: z.string(),
  }),
  execute: async (input) => {
    const result = await backendClient.getRecommendation(
      {
        candidate_name: input.candidateName,
        match_score: input.matchScore,
        match_rationale: input.matchRationale,
        interview_overall_score: input.interviewOverallScore ?? null,
        interview_score_breakdown: input.interviewScoreBreakdown ?? null,
        guardrails_passed: input.guardrailsPassed,
        bias_flags: input.biasFlags,
      },
      input.bearerToken
    );
    return {
      decision: result.decision as "strong_hire" | "hire" | "hold" | "no_hire",
      summary: result.summary,
      rationale: result.rationale,
    };
  },
});
