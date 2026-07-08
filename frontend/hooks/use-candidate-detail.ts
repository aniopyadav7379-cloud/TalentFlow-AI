"use client";

import { useQueries, useQuery } from "@tanstack/react-query";

import { applicationsApi, candidatesApi, jobsApi, resumesApi } from "@/lib/api-client";
import type { Application, Interview } from "@/types/application";
import type { Job } from "@/types/job";

export interface CandidateApplicationRow {
  application: Application;
  job: Job | null;
  interview: Interview | null;
}

/**
 * Aggregates everything the Candidate Details page needs, using only
 * endpoints that already exist:
 * - GET /candidates/{id}
 * - GET /resumes (filtered client-side by candidate_id — no per-candidate
 *   resume-list endpoint exists yet)
 * - GET /applications (filtered client-side by candidate_id, same reason)
 * - GET /jobs/{id} and GET /applications/{id}/interview per matched
 *   application, run in parallel via useQueries
 */
export function useCandidateDetail(candidateId: string) {
  const candidateQuery = useQuery({
    queryKey: ["candidates", candidateId],
    queryFn: () => candidatesApi.get(candidateId),
    enabled: !!candidateId,
  });

  const resumesQuery = useQuery({
    queryKey: ["resumes"],
    queryFn: () => resumesApi.list({ limit: 100 }),
    enabled: !!candidateId,
    select: (resumes) => resumes.filter((r) => r.candidate_id === candidateId),
  });

  const applicationsQuery = useQuery({
    queryKey: ["applications"],
    queryFn: () => applicationsApi.list({ limit: 100 }),
    enabled: !!candidateId,
    select: (applications) => applications.filter((a) => a.candidate_id === candidateId),
  });

  const applications = applicationsQuery.data ?? [];

  const jobQueries = useQueries({
    queries: applications.map((app) => ({
      queryKey: ["jobs", app.job_id],
      queryFn: () => jobsApi.get(app.job_id),
      enabled: !!candidateId,
    })),
  });

  const interviewQueries = useQueries({
    queries: applications.map((app) => ({
      queryKey: ["applications", app.id, "interview"],
      queryFn: () => applicationsApi.getInterview(app.id),
      enabled: !!candidateId,
      retry: false,
    })),
  });

  const rows: CandidateApplicationRow[] = applications.map((application, i) => ({
    application,
    job: jobQueries[i]?.data ?? null,
    interview: interviewQueries[i]?.data ?? null,
  }));

  return {
    candidate: candidateQuery.data,
    resumes: resumesQuery.data ?? [],
    applicationRows: rows,
    isLoading: candidateQuery.isLoading || resumesQuery.isLoading || applicationsQuery.isLoading,
    isError: candidateQuery.isError,
  };
}