import { serve } from "@hono/node-server";
import { Mastra } from "@mastra/core";
import { Hono } from "hono";
import { cors } from "hono/cors";

import { hiringAgent } from "./agents/hiringAgent.js";
import { config } from "./config/mastra.js";
import {
  interviewEvaluateWorkflow,
  interviewGenerateWorkflow,
} from "./workflows/interviewWorkflow.js";
import { hiringWorkflow } from "./workflows/hiringWorkflow.js";
import { recommendationWorkflow } from "./workflows/recommendationWorkflow.js";

export const mastra = new Mastra({
  agents: { hiringAgent },
  workflows: {
    hiringWorkflow,
    interviewGenerateWorkflow,
    interviewEvaluateWorkflow,
    recommendationWorkflow,
  },
});

// Suspended-run references live in-process for this demo/hackathon scope —
// good enough for a single-instance deployment where approve happens in the
// same process lifetime as trigger. A production deployment with multiple
// instances or restarts between trigger and approve would need Mastra's
// persistent storage adapter wired in here instead; not done in this pass
// (see mastra/README section "What's simplified for this pass").
const activeRuns = new Map<string, Awaited<ReturnType<typeof hiringWorkflow.createRun>>>();

function extractBearerToken(authHeader: string | undefined): string {
  if (!authHeader?.startsWith("Bearer ")) {
    throw new Error("Missing or malformed Authorization header — expected 'Bearer <recruiter JWT>'");
  }
  return authHeader.slice("Bearer ".length);
}

const app = new Hono();

// The frontend's browser (MastraAgentPanel, lib/mastra-client.ts) calls this
// service directly, cross-origin — without this, every browser request would
// be silently blocked by the browser's own CORS enforcement, even though
// curl/server-to-server calls (used in this project's own smoke testing)
// would appear to work fine, since CORS is a browser-only mechanism.
app.use(
  "*",
  cors({
    origin: config.corsOrigins,
    allowMethods: ["GET", "POST", "OPTIONS"],
    allowHeaders: ["Content-Type", "Authorization"],
  })
);

app.get("/health", (c) => c.json({ status: "ok", service: "talentflow-ai-mastra" }));

/**
 * Free-form agent chat — the agent decides which tools to call and in what
 * order. Matches the reference "Recruiter: Find Python Developers -> Agent
 * thinks -> calls tools" flow. For a deterministic, guaranteed call order
 * with a human-approval gate instead, use /workflows/hiring/trigger below.
 */
app.post("/agent/chat", async (c) => {
  const bearerToken = extractBearerToken(c.req.header("authorization"));
  const { message } = await c.req.json<{ message: string }>();
  const result = await hiringAgent.generate(`${message}\n\n(Use bearerToken="${bearerToken}" for every tool call.)`);
  return c.json({ text: result.text });
});

app.post("/workflows/hiring/trigger", async (c) => {
  const bearerToken = extractBearerToken(c.req.header("authorization"));
  const body = await c.req.json<{
    recruiterId: string;
    jobTitle: string;
    jobDescription?: string;
    jobSkills?: string[];
    topK?: number;
  }>();

  const run = await hiringWorkflow.createRun();
  activeRuns.set(run.runId, run);

  const result = await run.start({
    inputData: {
      recruiterId: body.recruiterId,
      jobTitle: body.jobTitle,
      jobDescription: body.jobDescription ?? "",
      jobSkills: body.jobSkills ?? [],
      topK: body.topK ?? 10,
      bearerToken,
    },
  });

  if (result.status === "suspended") {
    return c.json({
      runId: run.runId,
      status: "suspended",
      suspendedStep: result.suspended[0],
      approvalNeeded: result.steps["recruiter-approval"]?.suspendPayload,
    });
  }
  return c.json({ runId: run.runId, status: result.status, result: result.status === "success" ? result.result : undefined });
});

app.post("/workflows/hiring/:runId/approve", async (c) => {
  const runId = c.req.param("runId");
  const run = activeRuns.get(runId);
  if (!run) {
    return c.json({ error: `No active suspended run with id ${runId}. It may have already completed or the server restarted.` }, 404);
  }

  const { approved, approverName } = await c.req.json<{ approved: boolean; approverName?: string }>();
  const result = await run.resume({ step: "recruiter-approval", resumeData: { approved, approverName } });

  if (result.status !== "suspended") {
    activeRuns.delete(runId);
  }
  return c.json({ runId, status: result.status, result: result.status === "success" ? result.result : undefined });
});

app.post("/workflows/interview/generate", async (c) => {
  const bearerToken = extractBearerToken(c.req.header("authorization"));
  const body = await c.req.json<{ jobTitle: string; jobSkills?: string[]; candidateSkills?: string[]; numQuestions?: number }>();
  const run = await interviewGenerateWorkflow.createRun();
  const result = await run.start({
    inputData: {
      jobTitle: body.jobTitle,
      jobSkills: body.jobSkills ?? [],
      candidateSkills: body.candidateSkills,
      numQuestions: body.numQuestions ?? 5,
      bearerToken,
    },
  });
  return c.json(result);
});

app.post("/workflows/interview/evaluate", async (c) => {
  const bearerToken = extractBearerToken(c.req.header("authorization"));
  const body = await c.req.json<{ jobTitle: string; qaPairs: Array<{ questionId: string; question: string; answer: string }> }>();
  const run = await interviewEvaluateWorkflow.createRun();
  const result = await run.start({ inputData: { ...body, bearerToken } });
  return c.json(result);
});

app.post("/workflows/recommendation/trigger", async (c) => {
  const bearerToken = extractBearerToken(c.req.header("authorization"));
  const body = await c.req.json<{
    candidateName: string;
    matchScore: number;
    matchRationale?: string;
    interviewOverallScore?: number | null;
    interviewScoreBreakdown?: Record<string, number> | null;
  }>();
  const run = await recommendationWorkflow.createRun();
  const result = await run.start({
    inputData: {
      candidateName: body.candidateName,
      matchScore: body.matchScore,
      matchRationale: body.matchRationale ?? "",
      interviewOverallScore: body.interviewOverallScore ?? null,
      interviewScoreBreakdown: body.interviewScoreBreakdown ?? null,
      bearerToken,
    },
  });
  return c.json(result);
});

serve({ fetch: app.fetch, port: config.port }, (info) => {
  console.log(`talentflow-ai-mastra listening on http://localhost:${info.port}`);
  console.log(`Orchestrating backend at ${config.backendBaseUrl}`);
});
