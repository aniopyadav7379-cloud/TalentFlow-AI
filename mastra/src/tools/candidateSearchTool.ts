import { createTool } from "@mastra/core/tools";
import { z } from "zod";

import { backendClient } from "../services/backendClient.js";

export const candidateSearchTool = createTool({
  id: "search-candidates",
  description:
    "Semantically search uploaded resumes against a job description using Qdrant. Returns raw similarity matches — " +
    "use rankingTool afterward for a blended, recruiter-facing match score.",
  inputSchema: z.object({
    jobTitle: z.string(),
    jobDescription: z.string().default(""),
    jobSkills: z.array(z.string()).default([]),
    topK: z.number().int().min(1).max(100).default(10),
    bearerToken: z.string(),
  }),
  outputSchema: z.object({
    matches: z.array(
      z.object({
        resumeId: z.string(),
        candidateId: z.string(),
        score: z.number(),
        skills: z.array(z.string()),
      })
    ),
  }),
  execute: async (input) => {
    const result = await backendClient.searchCandidates(
      {
        job_title: input.jobTitle,
        job_description: input.jobDescription,
        job_skills: input.jobSkills,
        top_k: input.topK,
      },
      input.bearerToken
    );
    return {
      matches: result.matches.map((m) => ({
        resumeId: m.resume_id,
        candidateId: m.candidate_id,
        score: m.score,
        skills: m.skills,
      })),
    };
  },
});
