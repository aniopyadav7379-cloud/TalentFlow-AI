"use client";

import { useQuery } from "@tanstack/react-query";

import { interviewsApi } from "@/lib/api-client";

export function useInterviews() {
  return useQuery({ queryKey: ["interviews"], queryFn: () => interviewsApi.list({ limit: 100 }) });
}