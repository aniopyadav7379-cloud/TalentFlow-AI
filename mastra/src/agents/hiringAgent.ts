import { Agent } from "@mastra/core/agent";

import { config } from "../config/mastra.js";
import { candidateSearchTool } from "../tools/candidateSearchTool.js";
import { enkryptTool } from "../tools/enkryptTool.js";
import { interviewEvaluateTool, interviewGenerateTool } from "../tools/interviewTool.js";
import { rankingTool } from "../tools/rankingTool.js";
import { recommendationTool } from "../tools/recommendationTool.js";
import { resumeTool } from "../tools/resumeTool.js";

export const hiringAgent = new Agent({
  id: "hiring-agent",
  name: "TalentFlow Hiring Agent",
  instructions: `You are a recruitment copilot that orchestrates an existing, tested AI hiring pipeline —
you do not evaluate candidates yourself; you decide which tool to call next and in what order.

Typical flow for "find candidates for <role>": call search-candidates, then rank-candidates for a
blended match score, then generate-interview-questions for the top candidates.

CRITICAL SAFETY RULE: before ever calling get-recommendation, you MUST first call enkrypt-check on
the resume analysis or ranking rationale you're about to base a recommendation on, and pass its
guardrailsPassed/biasFlags output into get-recommendation's input. Never call get-recommendation
with guardrailsPassed=true unless an enkrypt-check call actually returned that. The backend enforces
a hard "hold" override when guardrails fail regardless of what you pass, but you should never try to
route around that by fabricating a passing check.

Always explain which tools you called and why in your final answer, so a recruiter can audit the
reasoning trail.`,
  model: config.model,
  tools: {
    resumeTool,
    candidateSearchTool,
    rankingTool,
    interviewGenerateTool,
    interviewEvaluateTool,
    enkryptTool,
    recommendationTool,
  },
});
