import { createTool } from "@mastra/core/tools";
import { z } from "zod";

import { backendClient } from "../services/backendClient.js";

export const interviewGenerateTool = createTool({
  id: "generate-interview-questions",
  description: "Generate role-specific interview questions for a job, optionally tailored to a candidate's known skills.",
  inputSchema: z.object({
    jobTitle: z.string(),
    jobSkills: z.array(z.string()).default([]),
    candidateSkills: z.array(z.string()).optional(),
    numQuestions: z.number().int().min(1).max(15).default(5),
    bearerToken: z.string(),
  }),
  outputSchema: z.object({
    questions: z.array(z.object({ id: z.string(), question: z.string(), category: z.string() })),
  }),
  execute: async (input) => {
    const result = await backendClient.generateInterviewQuestions(
      {
        job_title: input.jobTitle,
        job_skills: input.jobSkills,
        candidate_skills: input.candidateSkills,
        num_questions: input.numQuestions,
      },
      input.bearerToken
    );
    return { questions: result.questions };
  },
});

export const interviewEvaluateTool = createTool({
  id: "evaluate-interview-responses",
  description: "Score recorded interview question/answer pairs into a 5-dimension breakdown and an overall score.",
  inputSchema: z.object({
    jobTitle: z.string(),
    qaPairs: z
      .array(z.object({ questionId: z.string(), question: z.string(), answer: z.string() }))
      .min(1),
    bearerToken: z.string(),
  }),
  outputSchema: z.object({
    overallScore: z.number(),
    scoreBreakdown: z.record(z.string(), z.number()),
    summary: z.string(),
    perQuestion: z.array(z.object({ questionId: z.string(), score: z.number(), feedback: z.string() })),
  }),
  execute: async (input) => {
    const result = await backendClient.evaluateInterviewResponses(
      {
        job_title: input.jobTitle,
        qa_pairs: input.qaPairs.map((q) => ({ question_id: q.questionId, question: q.question, answer: q.answer })),
      },
      input.bearerToken
    );
    return {
      overallScore: result.overall_score,
      scoreBreakdown: result.score_breakdown,
      summary: result.summary,
      perQuestion: result.per_question.map((p) => ({ questionId: p.question_id, score: p.score, feedback: p.feedback })),
    };
  },
});
