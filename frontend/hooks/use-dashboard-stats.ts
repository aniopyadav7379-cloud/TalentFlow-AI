"use client";

import { useQuery } from "@tanstack/react-query";

import { jobsApi } from "@/lib/api-client";
import type { Application } from "@/types/application";
import type { Job } from "@/types/job";

export interface DashboardStats {
  totalJobs: number;
  openJobs: number;
  totalApplications: number;
  candidatesApplied: number;
  aiRanked: number;
  jobs: Job[];
}

/**
 * Aggregates dashboard numbers purely from endpoints that already exist
 * (GET /jobs and GET /jobs/{id}/applications for each job) — no new backend
 * routes required. This does mean one request per job to total up
 * applications, which is fine at hackathon scale; if the job list grows
 * large, a dedicated backend aggregate endpoint would be a better fit.
 */
export function useDashboardStats() {
  return useQuery({
    queryKey: ["dashboard-stats"],
    queryFn: async (): Promise<DashboardStats> => {
      const jobs = await jobsApi.list({ limit: 100 });

      const applicationsPerJob = await Promise.all(
        jobs.map((job) =>
          jobsApi.listApplications(job.id).catch(() => [] as Application[])
        )
      );

      const allApplications = applicationsPerJob.flat();
      const uniqueCandidateIds = new Set(allApplications.map((app) => app.candidate_id));

      return {
        totalJobs: jobs.length,
        openJobs: jobs.filter((job) => job.status === "open").length,
        totalApplications: allApplications.length,
        candidatesApplied: uniqueCandidateIds.size,
        aiRanked: allApplications.filter((app) => app.match_score !== null).length,
        jobs,
      };
    },
  });
}