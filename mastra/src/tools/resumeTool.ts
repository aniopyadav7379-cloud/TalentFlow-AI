import { createTool } from "@mastra/core/tools";
import { z } from "zod";

import { backendClient } from "../services/backendClient.js";

export const resumeTool = createTool({
  id: "upload-resume",
  description:
    "Upload a candidate's resume (base64-encoded PDF) to the backend. Parses skills/experience and embeds it for " +
    "semantic search — this delegates entirely to the existing FastAPI resume ingestion pipeline.",
  inputSchema: z.object({
    candidateId: z.string().describe("The candidate's existing ID in the backend"),
    fileBase64: z.string().describe("Base64-encoded PDF resume content"),
    fileName: z.string().default("resume.pdf"),
    bearerToken: z.string().describe("The recruiter's JWT, passed through to the backend"),
  }),
  outputSchema: z.object({
    resumeId: z.string(),
    parseStatus: z.string(),
    parsedSkills: z.array(z.string()),
    parsedExperienceYears: z.number().nullable(),
  }),
  execute: async (input) => {
    const result = await backendClient.uploadResume(
      input.candidateId,
      input.fileBase64,
      input.fileName,
      input.bearerToken
    );
    return {
      resumeId: result.id,
      parseStatus: result.parse_status,
      parsedSkills: result.parsed_skills,
      parsedExperienceYears: result.parsed_experience_years,
    };
  },
});
