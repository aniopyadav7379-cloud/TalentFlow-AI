/**
 * Standalone recommendation workflow: guardrail-check first, recommend
 * second — same ordering rule as hiringWorkflow.ts and for the same reason
 * (the recommendation step needs guardrailsPassed as INPUT to be able to
 * force a "hold"). Useful on its own once real interview scores exist
 * (see interviewWorkflow.ts's evaluate step) and a recommendation needs to
 * be re-synthesized with that real data, mirroring the backend's
 * `InterviewEvaluationPipeline._synthesize_and_evaluate`.
 */
import { createStep, createWorkflow } from "@mastra/core/workflows";
import { z } from "zod";

import { backendClient } from "../services/backendClient.js";

const guardrailCheckStep = createStep({
  id: "guardrail-check",
  inputSchema: z.object({
    candidateName: z.string(),
    matchScore: z.number(),
    matchRationale: z.string().default(""),
    interviewOverallScore: z.number().nullable().optional(),
    interviewScoreBreakdown: z.record(z.string(), z.number()).nullable().optional(),
    bearerToken: z.string(),
  }),
  outputSchema: z.object({
    candidateName: z.string(),
    matchScore: z.number(),
    matchRationale: z.string(),
    interviewOverallScore: z.number().nullable(),
    interviewScoreBreakdown: z.record(z.string(), z.number()).nullable(),
    bearerToken: z.string(),
    guardrailsPassed: z.boolean(),
    biasFlags: z.array(z.string()),
  }),
  execute: async ({ inputData }) => {
    const check = await backendClient.enkryptCheck({ text: inputData.matchRationale }, inputData.bearerToken);
    return {
      candidateName: inputData.candidateName,
      matchScore: inputData.matchScore,
      matchRationale: inputData.matchRationale,
      interviewOverallScore: inputData.interviewOverallScore ?? null,
      interviewScoreBreakdown: inputData.interviewScoreBreakdown ?? null,
      bearerToken: inputData.bearerToken,
      guardrailsPassed: check.passed_guardrails,
      biasFlags: check.bias_flags,
    };
  },
});

const recommendStep = createStep({
  id: "recommend",
  inputSchema: guardrailCheckStep.outputSchema,
  outputSchema: z.object({
    decision: z.string(),
    summary: z.string(),
    rationale: z.string(),
  }),
  execute: async ({ inputData }) => {
    const recommendation = await backendClient.getRecommendation(
      {
        candidate_name: inputData.candidateName,
        match_score: inputData.matchScore,
        match_rationale: inputData.matchRationale,
        interview_overall_score: inputData.interviewOverallScore,
        interview_score_breakdown: inputData.interviewScoreBreakdown,
        guardrails_passed: inputData.guardrailsPassed,
        bias_flags: inputData.biasFlags,
      },
      inputData.bearerToken
    );
    return recommendation;
  },
});

export const recommendationWorkflow = createWorkflow({
  id: "recommendation-workflow",
  inputSchema: guardrailCheckStep.inputSchema,
  outputSchema: recommendStep.outputSchema,
})
  .then(guardrailCheckStep)
  .then(recommendStep)
  .commit();
