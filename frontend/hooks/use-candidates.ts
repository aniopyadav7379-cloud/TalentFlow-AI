"use client";

import { useMutation } from "@tanstack/react-query";

import { candidatesApi } from "@/lib/api-client";
import type { CandidateCreatePayload } from "@/types/candidate";

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
