"use client";

import { useQuery } from "@tanstack/react-query";

import { usersApi } from "@/lib/api-client";
import { useAuth } from "@/providers/auth-provider";

export function useUsers() {
  const { user } = useAuth();
  return useQuery({
    queryKey: ["users"],
    queryFn: () => usersApi.list({ limit: 100 }),
    enabled: user?.role === "admin", // backend returns 403 for non-admins — don't even ask
  });
}