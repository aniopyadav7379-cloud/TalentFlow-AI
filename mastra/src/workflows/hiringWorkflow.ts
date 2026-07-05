/**
 * The main hiring workflow.
 *
 * Reference architecture order: Resume -> Candidate Search -> Ranking ->
 * Interview -> Recommendation -> Enkrypt -> Final Response.
 *
 * This implementation deviates from that literal order in one place, on
 * purpose: Enkrypt's guardrail check runs BEFORE the recommendation step,
 * not after, because `/recommendation`'s existing contract (see
 * backend/app/agents/hr_recommendation_agent.py, already built and tested
 * in Steps 3-4 of this project) takes `guardrailsPassed`/`biasFlags` as
 * INPUT and uses them to force a "hold" decision — it can't gate anything
 * if it only finds out about a guardrail failure after already deciding.
 * A second, optional Enkrypt check DOES run after the recommendation
 * (postGuardrailStep below), reviewing the recommendation's own rationale
 * for defense-in-depth — so the literal "Enkrypt after Recommendation"
 * arrow in the reference diagram is also present here, just not as the
 * ONLY guardrail check.
 *
 * Human-in-the-loop: execution suspends after ranking, presenting the top
 * candidate for recruiter approval, before any interview questions are
 * generated or any recommendation is synthesized. Rejecting the top
 * candidate short-circuits straight to a "no_hire" result without ever
 * calling the LLM-backed recommendation step.
 */
import { createStep, createWorkflow } from "@mastra/core/workflows";
import { z } from "zod";

import { backendClient } from "../services/backendClient.js";
import { rememberSearch } from "../memory/qdrantMemory.js";

const candidateSchema = z.object({
  resumeId: z.string(),
  candidateId: z.string(),
  matchScore: z.number(),
  matchedSkills: z.array(z.string()),
  missingSkills: z.array(z.string()),
  rationale: z.string(),
});

// Every step's output is a superset of the previous step's — each step adds
// fields, never drops earlier ones — so `.then()` chaining (next step's
// inputSchema = previous step's outputSchema) carries everything later
// steps need without relying on cross-step state APIs.

const rankStep = createStep({
  id: "rank-candidates",
  description: "Semantic + skill-overlap ranking via the backend's CandidateMatchingAgent (deterministic, no LLM).",
  inputSchema: z.object({
    recruiterId: z.string(),
    jobTitle: z.string(),
    jobDescription: z.string().default(""),
    jobSkills: z.array(z.string()).default([]),
    topK: z.number().int().min(1).max(100).default(10),
    bearerToken: z.string(),
  }),
  outputSchema: z.object({
    recruiterId: z.string(),
    jobTitle: z.string(),
    bearerToken: z.string(),
    candidates: z.array(candidateSchema),
    topCandidate: candidateSchema.nullable(),
  }),
  execute: async ({ inputData }) => {
    const ranked = await backendClient.rankCandidates(
      {
        job_title: inputData.jobTitle,
        job_description: inputData.jobDescription,
        job_skills: inputData.jobSkills,
        top_k: inputData.topK,
      },
      inputData.bearerToken
    );
    const candidates = ranked.map((r) => ({
      resumeId: r.resume_id,
      candidateId: r.candidate_id,
      matchScore: r.match_score,
      matchedSkills: r.matched_skills,
      missingSkills: r.missing_skills,
      rationale: r.rationale,
    }));

    await rememberSearch(inputData.recruiterId, inputData.jobTitle, inputData.jobSkills).catch(() => {
      // Memory is best-effort — a Qdrant/OpenAI hiccup here must never fail the whole hiring workflow.
    });

    return {
      recruiterId: inputData.recruiterId,
      jobTitle: inputData.jobTitle,
      bearerToken: inputData.bearerToken,
      candidates,
      topCandidate: candidates[0] ?? null,
    };
  },
});

const guardrailPreCheckStep = createStep({
  id: "guardrail-pre-check",
  description: "Fairness-checks the top candidate's ranking rationale BEFORE any recommendation is generated.",
  inputSchema: rankStep.outputSchema,
  outputSchema: z.object({
    recruiterId: z.string(),
    jobTitle: z.string(),
    bearerToken: z.string(),
    candidates: z.array(candidateSchema),
    topCandidate: candidateSchema.nullable(),
    guardrailsPassed: z.boolean(),
    biasFlags: z.array(z.string()),
  }),
  execute: async ({ inputData }) => {
    if (!inputData.topCandidate) {
      return { ...inputData, guardrailsPassed: false, biasFlags: ["no_candidates_found"] };
    }
    const check = await backendClient.enkryptCheck(
      { text: inputData.topCandidate.rationale },
      inputData.bearerToken
    );
    return { ...inputData, guardrailsPassed: check.passed_guardrails, biasFlags: check.bias_flags };
  },
});

const approvalStep = createStep({
  id: "recruiter-approval",
  description: "Suspends the workflow for human approval of the top candidate before proceeding.",
  inputSchema: guardrailPreCheckStep.outputSchema,
  outputSchema: z.object({
    recruiterId: z.string(),
    jobTitle: z.string(),
    bearerToken: z.string(),
    candidates: z.array(candidateSchema),
    topCandidate: candidateSchema.nullable(),
    guardrailsPassed: z.boolean(),
    biasFlags: z.array(z.string()),
    approved: z.boolean(),
    approverName: z.string().optional(),
  }),
  suspendSchema: z.object({
    topCandidateId: z.string().nullable(),
    matchScore: z.number().nullable(),
    guardrailsPassed: z.boolean(),
    biasFlags: z.array(z.string()),
    reason: z.string(),
  }),
  resumeSchema: z.object({
    approved: z.boolean(),
    approverName: z.string().optional(),
  }),
  execute: async ({ inputData, resumeData, suspend }) => {
    if (resumeData) {
      return { ...inputData, approved: resumeData.approved, approverName: resumeData.approverName };
    }
    return await suspend({
      topCandidateId: inputData.topCandidate?.candidateId ?? null,
      matchScore: inputData.topCandidate?.matchScore ?? null,
      guardrailsPassed: inputData.guardrailsPassed,
      biasFlags: inputData.biasFlags,
      reason: inputData.guardrailsPassed
        ? "Awaiting recruiter approval of the top-ranked candidate."
        : "Guardrail check flagged a concern — review carefully before approving.",
    });
  },
});

const recommendationStep = createStep({
  id: "synthesize-recommendation",
  description: "Generates interview questions and a hiring recommendation for the approved candidate only.",
  inputSchema: approvalStep.outputSchema,
  outputSchema: z.object({
    candidateId: z.string().nullable(),
    questions: z.array(z.object({ id: z.string(), question: z.string(), category: z.string() })),
    decision: z.string(),
    summary: z.string(),
    rationale: z.string(),
    bearerToken: z.string(),
  }),
  execute: async ({ inputData }) => {
    if (!inputData.approved || !inputData.topCandidate) {
      return {
        candidateId: inputData.topCandidate?.candidateId ?? null,
        questions: [],
        decision: "no_hire",
        summary: "Rejected by recruiter before a recommendation was generated.",
        rationale: `Human reviewer${inputData.approverName ? ` (${inputData.approverName})` : ""} did not approve the top candidate.`,
        bearerToken: inputData.bearerToken,
      };
    }

    const candidate = await backendClient.getCandidate(inputData.topCandidate.candidateId, inputData.bearerToken);
    const questionResult = await backendClient.generateInterviewQuestions(
      { job_title: inputData.jobTitle, job_skills: [], candidate_skills: inputData.topCandidate.matchedSkills },
      inputData.bearerToken
    );
    const recommendation = await backendClient.getRecommendation(
      {
        candidate_name: candidate.full_name,
        match_score: inputData.topCandidate.matchScore,
        match_rationale: inputData.topCandidate.rationale,
        guardrails_passed: inputData.guardrailsPassed,
        bias_flags: inputData.biasFlags,
      },
      inputData.bearerToken
    );

    return {
      candidateId: inputData.topCandidate.candidateId,
      questions: questionResult.questions,
      decision: recommendation.decision,
      summary: recommendation.summary,
      rationale: recommendation.rationale,
      bearerToken: inputData.bearerToken,
    };
  },
});

const postGuardrailStep = createStep({
  id: "guardrail-post-check",
  description:
    "Defense-in-depth: fairness/grounding-checks the RECOMMENDATION's own rationale after it's generated " +
    "(matches the reference architecture's literal 'Enkrypt after Recommendation' step).",
  inputSchema: recommendationStep.outputSchema,
  outputSchema: z.object({
    candidateId: z.string().nullable(),
    questions: z.array(z.object({ id: z.string(), question: z.string(), category: z.string() })),
    decision: z.string(),
    summary: z.string(),
    rationale: z.string(),
    postCheckPassed: z.boolean(),
    postCheckBiasFlags: z.array(z.string()),
  }),
  execute: async ({ inputData }) => {
    if (inputData.decision === "no_hire" && inputData.rationale.includes("did not approve")) {
      // Rejected before a real recommendation existed — nothing to post-check.
      return { ...inputData, postCheckPassed: true, postCheckBiasFlags: [] };
    }

    const check = await backendClient.enkryptCheck(
      {
        text: inputData.rationale,
        source_text: `Decision: ${inputData.decision}. Summary: ${inputData.summary}`,
      },
      inputData.bearerToken
    );

    let decision = inputData.decision;
    let rationale = inputData.rationale;
    if (!check.passed_guardrails && (decision === "strong_hire" || decision === "hire")) {
      decision = "hold";
      rationale = `Held for human review — the post-hoc guardrail check flagged the recommendation rationale (${check.bias_flags.join(", ") || "unspecified"}). Original rationale: ${rationale}`;
    }

    return {
      candidateId: inputData.candidateId,
      questions: inputData.questions,
      decision,
      summary: inputData.summary,
      rationale,
      postCheckPassed: check.passed_guardrails,
      postCheckBiasFlags: check.bias_flags,
    };
  },
});

export const hiringWorkflow = createWorkflow({
  id: "hiring-workflow",
  inputSchema: rankStep.inputSchema,
  outputSchema: postGuardrailStep.outputSchema,
})
  .then(rankStep)
  .then(guardrailPreCheckStep)
  .then(approvalStep)
  .then(recommendationStep)
  .then(postGuardrailStep)
  .commit();
