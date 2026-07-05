import { createTool } from "@mastra/core/tools";
import { z } from "zod";

import { backendClient } from "../services/backendClient.js";

export const rankingTool = createTool({
  id: "rank-candidates",
  description:
    "Rank candidates for a job with a blended semantic-similarity + skill-overlap match score (0-100). " +
    "Deterministic — the backend's CandidateMatchingAgent does not call an LLM for this.",
  inputSchema: z.object({
    jobTitle: z.string(),
    jobDescription: z.string().default(""),
    jobSkills: z.array(z.string()).default([]),
    topK: z.number().int().min(1).max(100).default(10),
    bearerToken: z.string(),
  }),
  outputSchema: z.object({
    ranked: z.array(
      z.object({
        resumeId: z.string(),
        candidateId: z.string(),
        matchScore: z.number(),
        matchedSkills: z.array(z.string()),
        missingSkills: z.array(z.string()),
        rationale: z.string(),
      })
    ),
  }),
  execute: async (input) => {
    const result = await backendClient.rankCandidates(
      {
        job_title: input.jobTitle,
        job_description: input.jobDescription,
        job_skills: input.jobSkills,
        top_k: input.topK,
      },
      input.bearerToken
    );
    return {
      ranked: result.map((r) => ({
        resumeId: r.resume_id,
        candidateId: r.candidate_id,
        matchScore: r.match_score,
        matchedSkills: r.matched_skills,
        missingSkills: r.missing_skills,
        rationale: r.rationale,
      })),
    };
  },
});
