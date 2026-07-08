"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { candidatesApi } from "@/lib/api-client";
import type { CandidateCreatePayload } from "@/types/candidate";

export function useCandidates() {
  return useQuery({ queryKey: ["candidates"], queryFn: () => candidatesApi.list({ limit: 100 }) });
}

export function useCandidate(candidateId: string) {
  return useQuery({
    queryKey: ["candidates", candidateId],
    queryFn: () => candidatesApi.get(candidateId),
    enabled: !!candidateId,
  });
}

export function useDeleteCandidate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (candidateId: string) => candidatesApi.delete(candidateId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["candidates"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard-stats"] });
    },
  });
}

export function useCreateCandidate() {
  return useMutation({
    mutationFn: (payload: CandidateCreatePayload) => candidatesApi.create(payload),
  });
}

export function useUploadResume() {
  return useMutation({
    mutationFn: ({ candidateId, file }: { candidateId: string; file: File }) =>
      candidatesApi.uploadResume(candidateId, file),
  });
}