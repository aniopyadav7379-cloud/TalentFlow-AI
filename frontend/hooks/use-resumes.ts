"use client";

import { useQuery } from "@tanstack/react-query";

import { resumesApi } from "@/lib/api-client";

export function useResumes() {
  return useQuery({ queryKey: ["resumes"], queryFn: () => resumesApi.list({ limit: 100 }) });
}