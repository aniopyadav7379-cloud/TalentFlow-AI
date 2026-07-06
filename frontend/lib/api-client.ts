import { clearToken, getToken } from "@/lib/auth-storage";
import type { LoginPayload, RegisterPayload, TokenResponse, User } from "@/types/auth";
import type { Candidate, CandidateCreatePayload, Resume } from "@/types/candidate";
import type {
  Application,
  Interview,
  InterviewResponsePayload,
  ShortlistEntry,
} from "@/types/application";
import type { Job, JobCreatePayload, JobUpdatePayload } from "@/types/job";

const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "https://talentflow-ai-backend-007t.onrender.com/api/v1";

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
    this.detail = detail;
    this.name = "ApiError";
  }
}

async function request<T>(
  path: string,
  options: RequestInit & { auth?: boolean } = {}
): Promise<T> {
  const { auth = true, headers, ...rest } = options;
  const finalHeaders = new Headers(headers);

  if (auth) {
    const token = getToken();
    if (token) finalHeaders.set("Authorization", `Bearer ${token}`);
  }
  if (!(rest.body instanceof FormData) && rest.body !== undefined) {
    finalHeaders.set("Content-Type", "application/json");
  }

  const response = await fetch(`${BASE_URL}${path}`, { ...rest, headers: finalHeaders });

  if (response.status === 401 && auth) {
    // Token is missing/expired/invalid — clear it so the app doesn't keep
    // retrying with a dead token, and let the caller's UI redirect to login.
    clearToken();
  }

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail ?? detail;
    } catch {
      // Response wasn't JSON — fall back to statusText, already set above.
    }
    throw new ApiError(response.status, detail);
  }

  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

// ---------------------------------------------------------------------- //
// Auth
// ---------------------------------------------------------------------- //

export const authApi = {
  register: (payload: RegisterPayload) =>
    request<User>("/auth/register", { method: "POST", body: JSON.stringify(payload), auth: false }),

  login: (payload: LoginPayload) =>
    request<TokenResponse>("/auth/login", { method: "POST", body: JSON.stringify(payload), auth: false }),

  me: () => request<User>("/auth/me"),
};

// ---------------------------------------------------------------------- //
// Jobs
// ---------------------------------------------------------------------- //

export const jobsApi = {
  list: (params?: { skip?: number; limit?: number }) => {
    const query = new URLSearchParams();
    if (params?.skip) query.set("skip", String(params.skip));
    if (params?.limit) query.set("limit", String(params.limit));
    const qs = query.toString();
    return request<Job[]>(`/jobs${qs ? `?${qs}` : ""}`);
  },

  get: (jobId: string) => request<Job>(`/jobs/${jobId}`),

  create: (payload: JobCreatePayload) =>
    request<Job>("/jobs", { method: "POST", body: JSON.stringify(payload) }),

  update: (jobId: string, payload: JobUpdatePayload) =>
    request<Job>(`/jobs/${jobId}`, { method: "PATCH", body: JSON.stringify(payload) }),

  runShortlist: (jobId: string, topK = 10) =>
    request<ShortlistEntry[]>(`/jobs/${jobId}/shortlist`, {
      method: "POST",
      body: JSON.stringify({ top_k: topK }),
    }),

  listApplications: (jobId: string) => request<Application[]>(`/jobs/${jobId}/applications`),
};

// ---------------------------------------------------------------------- //
// Candidates
// ---------------------------------------------------------------------- //

export const candidatesApi = {
  create: (payload: CandidateCreatePayload) =>
    request<Candidate>("/candidates", { method: "POST", body: JSON.stringify(payload) }),

  get: (candidateId: string) => request<Candidate>(`/candidates/${candidateId}`),

  uploadResume: (candidateId: string, file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return request<Resume>(`/candidates/${candidateId}/resume`, { method: "POST", body: formData });
  },
};

// ---------------------------------------------------------------------- //
// Applications & Interviews
// ---------------------------------------------------------------------- //

export const applicationsApi = {
  get: (applicationId: string) => request<Application>(`/applications/${applicationId}`),

  getInterview: (applicationId: string) => request<Interview>(`/applications/${applicationId}/interview`),

  submitInterviewResponses: (applicationId: string, responses: InterviewResponsePayload[]) =>
    request<Interview>(`/applications/${applicationId}/interview/responses`, {
      method: "POST",
      body: JSON.stringify({ responses }),
    }),
};
