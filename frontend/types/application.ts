export type ApplicationStatus =
  | "submitted"
  | "shortlisted"
  | "interviewing"
  | "offered"
  | "rejected"
  | "withdrawn";

export interface Application {
  id: string;
  job_id: string;
  candidate_id: string;
  resume_id: string | null;
  status: ApplicationStatus;
  match_score: number | null;
  match_rationale: string | null;
  ai_summary: string | null;
  created_at: string;
  updated_at: string;
}

/** The recruiter-facing ranked shortlist row — the primary output of the shortlist pipeline. */
export interface ShortlistEntry {
  application_id: string;
  candidate_id: string;
  candidate_name: string;
  match_score: number;
  match_rationale: string;
  top_skills: string[];
  passed_guardrails: boolean;
  bias_flags: string[];
  recommendation: string;
}

export type InterviewStatus = "pending" | "scheduled" | "in_progress" | "completed" | "cancelled";

export interface InterviewQuestion {
  id: string;
  question: string;
  category: "technical" | "behavioral" | "system_design" | "problem_solving" | "culture_fit";
}

export interface ScoreBreakdown {
  technical: number;
  communication: number;
  problem_solving: number;
  confidence: number;
  leadership: number;
}

export interface InterviewResponseRecord {
  id: string;
  question: string;
  answer: string | null;
  score: number | null;
  feedback: string | null;
}

export interface Interview {
  id: string;
  application_id: string;
  status: InterviewStatus;
  questions: InterviewQuestion[];
  overall_score: number | null;
  score_breakdown: ScoreBreakdown | Record<string, never>;
  ai_recommendation: string | null;
  created_at: string;
  responses: InterviewResponseRecord[];
}

export interface InterviewResponsePayload {
  question_id: string;
  question: string;
  answer: string;
}

export interface Evaluation {
  id: string;
  application_id: string;
  fairness_score: number | null;
  bias_flags: string[];
  grounding_score: number | null;
  passed_guardrails: boolean;
  final_recommendation: string | null;
  created_at: string;
}