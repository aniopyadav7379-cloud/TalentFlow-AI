"use client";

import { useQuery } from "@tanstack/react-query";

import { applicationsApi } from "@/lib/api-client";

export function useApplications() {
  return useQuery({ queryKey: ["applications"], queryFn: () => applicationsApi.list({ limit: 100 }) });
}

export function useApplication(applicationId: string) {
  return useQuery({
    queryKey: ["applications", applicationId],
    queryFn: () => applicationsApi.get(applicationId),
    enabled: !!applicationId,
  });
}

export function useApplicationInterview(applicationId: string) {
  return useQuery({
    queryKey: ["applications", applicationId, "interview"],
    queryFn: () => applicationsApi.getInterview(applicationId),
    enabled: !!applicationId,
    retry: false, // 404 just means no interview generated yet — not worth retrying
  });
}