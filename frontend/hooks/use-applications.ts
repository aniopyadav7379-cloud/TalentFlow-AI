"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { applicationsApi } from "@/lib/api-client";
import type { InterviewResponsePayload } from "@/types/application";

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

export function useSubmitInterviewResponses(applicationId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (responses: InterviewResponsePayload[]) =>
      applicationsApi.submitInterviewResponses(applicationId, responses),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["applications", applicationId, "interview"] });
      queryClient.invalidateQueries({ queryKey: ["interviews"] });
      queryClient.invalidateQueries({ queryKey: ["evaluations"] });
    },
  });
}