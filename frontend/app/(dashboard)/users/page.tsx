"use client";

import { Users as UsersIcon } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { EmptyState, ErrorAlert, Spinner } from "@/components/ui/feedback";
import { useUsers } from "@/hooks/use-users";
import { useAuth } from "@/providers/auth-provider";

export default function UsersPage() {
  const { user } = useAuth();
  const { data: users, isLoading, isError } = useUsers();

  if (user && user.role !== "admin") {
    return (
      <EmptyState
        icon={<UsersIcon className="h-6 w-6" />}
        title="Admin access required"
        description="Only admin accounts can view the user directory."
      />
    );
  }

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-foreground">Users</h1>
        <p className="text-sm text-muted-foreground">Everyone with access to TalentFlow AI.</p>
      </div>

      {isLoading && (
        <div className="flex justify-center py-16">
          <Spinner />
        </div>
      )}

      {isError && <ErrorAlert message="Couldn't load users." />}

      {users && users.length > 0 && (
        <Card className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-border text-xs uppercase tracking-wide text-muted">
                  <th className="px-5 py-3 font-medium">Name</th>
                  <th className="px-5 py-3 font-medium">Email</th>
                  <th className="px-5 py-3 font-medium">Role</th>
                  <th className="px-5 py-3 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.id} className="border-b border-border/60 last:border-0">
                    <td className="px-5 py-3 font-medium text-foreground">{u.full_name}</td>
                    <td className="px-5 py-3 text-muted-foreground">{u.email}</td>
                    <td className="px-5 py-3">
                      <Badge variant="accent">{u.role}</Badge>
                    </td>
                    <td className="px-5 py-3">
                      <Badge variant={u.is_active ? "success" : "default"}>
                        {u.is_active ? "Active" : "Inactive"}
                      </Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}