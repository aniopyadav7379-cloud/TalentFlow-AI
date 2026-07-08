"use client";

import { useQuery } from "@tanstack/react-query";

import { evaluationsApi } from "@/lib/api-client";

export function useEvaluations() {
  return useQuery({ queryKey: ["evaluations"], queryFn: () => evaluationsApi.list({ limit: 100 }) });
}