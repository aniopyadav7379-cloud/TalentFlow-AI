export interface Candidate {
  id: string;
  full_name: string;
  email: string;
  phone: string | null;
  created_at: string;
}

export interface CandidateCreatePayload {
  full_name: string;
  email: string;
  phone?: string;
}

export type ResumeParseStatus = "pending" | "parsed" | "failed";

export interface Resume {
  id: string;
  candidate_id: string;
  file_url: string;
  parsed_skills: string[];
  parsed_experience_years: number | null;
  parsed_education: Record<string, string>[];
  parse_status: ResumeParseStatus;
  created_at: string;
}
