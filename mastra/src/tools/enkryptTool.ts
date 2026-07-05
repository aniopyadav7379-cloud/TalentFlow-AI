import { createTool } from "@mastra/core/tools";
import { z } from "zod";

import { backendClient } from "../services/backendClient.js";

export const enkryptTool = createTool({
  id: "enkrypt-check",
  description:
    "Run a fairness/bias check (and, if source text is given, a grounding/hallucination check) on AI-generated text " +
    "via Enkrypt AI, through the backend's guardrail layer. This is the tool that can force a hiring recommendation " +
    "to a 'hold' decision — see hiringWorkflow.ts for why it must run BEFORE recommendationTool, not after.",
  inputSchema: z.object({
    text: z.string().min(1).describe("AI-generated text to check, e.g. a resume analysis or a recommendation rationale"),
    sourceText: z.string().optional().describe("If provided, also grounds `text` against this evidence"),
    bearerToken: z.string(),
  }),
  outputSchema: z.object({
    fairnessScore: z.number(),
    groundingScore: z.number(),
    biasFlags: z.array(z.string()),
    passedGuardrails: z.boolean(),
  }),
  execute: async (input) => {
    const result = await backendClient.enkryptCheck(
      { text: input.text, source_text: input.sourceText },
      input.bearerToken
    );
    return {
      fairnessScore: result.fairness_score,
      groundingScore: result.grounding_score,
      biasFlags: result.bias_flags,
      passedGuardrails: result.passed_guardrails,
    };
  },
});
