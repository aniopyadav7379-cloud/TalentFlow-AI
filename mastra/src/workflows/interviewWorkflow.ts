/**
 * Standalone interview workflow: generate questions now, evaluate answers
 * later once a human has actually conducted the interview. This mirrors
 * the backend's own architecture — `ShortlistPipeline` generates questions,
 * `InterviewEvaluationPipeline` scores them once responses exist, as two
 * separate pipelines because a real interview happens between them, not
 * synchronously in one request. `hiringWorkflow.ts` already includes a
 * question-generation step inline; this workflow exists for triggering
 * generation or evaluation independently (e.g. from the interviews UI).
 */
import { createStep, createWorkflow } from "@mastra/core/workflows";
import { z } from "zod";

import { backendClient } from "../services/backendClient.js";

const generateStep = createStep({
  id: "generate-questions",
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
  execute: async ({ inputData }) => {
    const result = await backendClient.generateInterviewQuestions(
      {
        job_title: inputData.jobTitle,
        job_skills: inputData.jobSkills,
        candidate_skills: inputData.candidateSkills,
        num_questions: inputData.numQuestions,
      },
      inputData.bearerToken
    );
    return { questions: result.questions };
  },
});

export const interviewGenerateWorkflow = createWorkflow({
  id: "interview-generate-workflow",
  inputSchema: generateStep.inputSchema,
  outputSchema: generateStep.outputSchema,
})
  .then(generateStep)
  .commit();

const evaluateStep = createStep({
  id: "evaluate-responses",
  inputSchema: z.object({
    jobTitle: z.string(),
    qaPairs: z.array(z.object({ questionId: z.string(), question: z.string(), answer: z.string() })).min(1),
    bearerToken: z.string(),
  }),
  outputSchema: z.object({
    overallScore: z.number(),
    scoreBreakdown: z.record(z.string(), z.number()),
    summary: z.string(),
  }),
  execute: async ({ inputData }) => {
    const result = await backendClient.evaluateInterviewResponses(
      {
        job_title: inputData.jobTitle,
        qa_pairs: inputData.qaPairs.map((q) => ({ question_id: q.questionId, question: q.question, answer: q.answer })),
      },
      inputData.bearerToken
    );
    return { overallScore: result.overall_score, scoreBreakdown: result.score_breakdown, summary: result.summary };
  },
});

export const interviewEvaluateWorkflow = createWorkflow({
  id: "interview-evaluate-workflow",
  inputSchema: evaluateStep.inputSchema,
  outputSchema: evaluateStep.outputSchema,
})
  .then(evaluateStep)
  .commit();
