"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { jobsApi } from "@/lib/api-client";
import type { JobCreatePayload, JobUpdatePayload } from "@/types/job";

export function useJobs() {
  return useQuery({ queryKey: ["jobs"], queryFn: () => jobsApi.list({ limit: 100 }) });
}

export function useJob(jobId: string) {
  return useQuery({ queryKey: ["jobs", jobId], queryFn: () => jobsApi.get(jobId), enabled: !!jobId });
}

export function useCreateJob() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: JobCreatePayload) => jobsApi.create(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
    },
  });
}

export function useUpdateJob(jobId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: JobUpdatePayload) => jobsApi.update(jobId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      queryClient.invalidateQueries({ queryKey: ["jobs", jobId] });
    },
  });
}

export function useRunShortlist(jobId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (topK: number) => jobsApi.runShortlist(jobId, topK),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["jobs", jobId, "applications"] });
    },
  });
}

export function useJobApplications(jobId: string) {
  return useQuery({
    queryKey: ["jobs", jobId, "applications"],
    queryFn: () => jobsApi.listApplications(jobId),
    enabled: !!jobId,
  });
}
