import { config } from "../config/mastra.js";

export class BackendError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "BackendError";
  }
}

async function request<T>(path: string, bearerToken: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${bearerToken}`);
  if (init.body !== undefined && !(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${config.backendBaseUrl}${path}`, { ...init, headers });

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = (await response.json()) as { detail?: string };
      detail = body.detail ?? detail;
    } catch {
      // Response wasn't JSON — fall back to statusText already set above.
    }
    throw new BackendError(response.status, detail);
  }
  return response.json() as Promise<T>;
}

/**
 * All calls take `bearerToken` explicitly rather than reading a shared
 * service-account token — this Mastra service orchestrates ON BEHALF OF a
 * recruiter's own session, using their existing JWT from the frontend, so
 * every backend call is subject to the exact same auth the recruiter
 * already has. No new trust boundary or backdoor auth path is introduced.
 */
export const backendClient = {
  getCandidate(candidateId: string, bearerToken: string) {
    return request<{ id: string; full_name: string; email: string }>(`/candidates/${candidateId}`, bearerToken);
  },

  uploadResume(candidateId: string, fileBase64: string, fileName: string, bearerToken: string) {
    const buffer = Buffer.from(fileBase64, "base64");
    const blob = new Blob([buffer], { type: "application/pdf" });
    const formData = new FormData();
    formData.append("file", blob, fileName);
    return request<{
      id: string;
      candidate_id: string;
      parse_status: string;
      parsed_skills: string[];
      parsed_experience_years: number | null;
    }>(`/candidates/${candidateId}/resume`, bearerToken, { method: "POST", body: formData });
  },

  searchCandidates(
    payload: { job_title: string; job_description?: string; job_skills?: string[]; top_k?: number },
    bearerToken: string
  ) {
    return request<{ matches: Array<{ resume_id: string; candidate_id: string; score: number; skills: string[] }> }>(
      "/candidate/search",
      bearerToken,
      { method: "POST", body: JSON.stringify(payload) }
    );
  },

  rankCandidates(
    payload: { job_title: string; job_description?: string; job_skills?: string[]; top_k?: number },
    bearerToken: string
  ) {
    return request<
      Array<{
        resume_id: string;
        candidate_id: string;
        semantic_score: number;
        skill_overlap_score: number;
        match_score: number;
        matched_skills: string[];
        missing_skills: string[];
        rationale: string;
      }>
    >("/candidate/rank", bearerToken, { method: "POST", body: JSON.stringify(payload) });
  },

  generateInterviewQuestions(
    payload: { job_title: string; job_skills?: string[]; candidate_skills?: string[]; num_questions?: number },
    bearerToken: string
  ) {
    return request<{ questions: Array<{ id: string; question: string; category: string }> }>(
      "/interview/generate",
      bearerToken,
      { method: "POST", body: JSON.stringify(payload) }
    );
  },

  evaluateInterviewResponses(
    payload: { job_title: string; qa_pairs: Array<{ question_id: string; question: string; answer: string }> },
    bearerToken: string
  ) {
    return request<{
      per_question: Array<{ question_id: string; score: number; feedback: string }>;
      score_breakdown: Record<string, number>;
      overall_score: number;
      summary: string;
    }>("/interview/evaluate", bearerToken, { method: "POST", body: JSON.stringify(payload) });
  },

  getRecommendation(
    payload: {
      candidate_name: string;
      match_score: number;
      match_rationale?: string;
      interview_overall_score?: number | null;
      interview_score_breakdown?: Record<string, number> | null;
      guardrails_passed: boolean;
      bias_flags?: string[];
    },
    bearerToken: string
  ) {
    return request<{ decision: string; summary: string; rationale: string }>("/recommendation", bearerToken, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  enkryptCheck(payload: { text: string; source_text?: string; context?: Record<string, unknown> }, bearerToken: string) {
    return request<{
      fairness_score: number;
      bias_flags: string[];
      grounding_score: number;
      passed_guardrails: boolean;
      raw_report: Record<string, unknown>;
    }>("/enkrypt/check", bearerToken, { method: "POST", body: JSON.stringify(payload) });
  },
};
