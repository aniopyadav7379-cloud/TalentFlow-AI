export type JobStatus = "draft" | "open" | "closed" | "archived";

export interface Job {
  id: string;
  title: string;
  department: string | null;
  description: string;
  requirements: string | null;
  skills: string[];
  experience_level: string | null;
  salary_min: number | null;
  salary_max: number | null;
  location: string | null;
  employment_type: string | null;
  status: JobStatus;
  created_by_id: string;
  created_at: string;
  updated_at: string;
}

export interface JobCreatePayload {
  title: string;
  department?: string;
  description: string;
  requirements?: string;
  skills?: string[];
  experience_level?: string;
  salary_min?: number;
  salary_max?: number;
  location?: string;
  employment_type?: string;
}

export type JobUpdatePayload = Partial<JobCreatePayload> & { status?: JobStatus };
