"use client";

import { Plus, Trash2, UserRound } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState, ErrorAlert, Spinner } from "@/components/ui/feedback";
import { useCandidates, useDeleteCandidate } from "@/hooks/use-candidates";
import { ApiError } from "@/lib/api-client";

export default function CandidatesPage() {
  const { data: candidates, isLoading, isError } = useCandidates();
  const deleteCandidate = useDeleteCandidate();
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [pendingId, setPendingId] = useState<string | null>(null);

  async function handleDelete(candidateId: string, name: string) {
    if (!window.confirm(`Delete ${name}? This also removes their resumes and applications.`)) return;
    setDeleteError(null);
    setPendingId(candidateId);
    try {
      await deleteCandidate.mutateAsync(candidateId);
    } catch (err) {
      setDeleteError(err instanceof ApiError ? err.detail : "Couldn't delete this candidate. Please try again.");
    } finally {
      setPendingId(null);
    }
  }

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-foreground">Candidates</h1>
          <p className="text-sm text-muted-foreground">Everyone who has been added to TalentFlow AI.</p>
        </div>
        <Link href="/candidates/add">
          <Button>
            <Plus className="h-4 w-4" />
            Add Candidate
          </Button>
        </Link>
      </div>

      {deleteError && (
        <div className="mb-4">
          <ErrorAlert message={deleteError} />
        </div>
      )}

      {isLoading && (
        <div className="flex justify-center py-16">
          <Spinner />
        </div>
      )}

      {isError && <ErrorAlert message="Couldn't load candidates. Check that the backend is running." />}

      {candidates && candidates.length === 0 && (
        <EmptyState
          icon={<UserRound className="h-6 w-6" />}
          title="No candidates yet"
          description="Add your first candidate to start matching them against jobs."
          action={
            <Link href="/candidates/add">
              <Button size="sm">Add Candidate</Button>
            </Link>
          }
        />
      )}

      {candidates && candidates.length > 0 && (
        <Card className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-border text-xs uppercase tracking-wide text-muted">
                  <th className="px-5 py-3 font-medium">Name</th>
                  <th className="px-5 py-3 font-medium">Email</th>
                  <th className="px-5 py-3 font-medium">Phone</th>
                  <th className="px-5 py-3 font-medium">Added</th>
                  <th className="px-5 py-3 font-medium text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {candidates.map((candidate) => (
                  <tr key={candidate.id} className="border-b border-border/60 last:border-0">
                    <td className="px-5 py-3">
                      <Link
                        href={`/candidates/${candidate.id}`}
                        className="font-medium text-foreground hover:text-primary"
                      >
                        {candidate.full_name}
                      </Link>
                    </td>
                    <td className="px-5 py-3 text-muted-foreground">{candidate.email}</td>
                    <td className="px-5 py-3 text-muted-foreground">{candidate.phone ?? "—"}</td>
                    <td className="px-5 py-3 text-muted-foreground">
                      {new Date(candidate.created_at).toLocaleDateString()}
                    </td>
                    <td className="px-5 py-3">
                      <div className="flex justify-end gap-2">
                        <Link href={`/candidates/${candidate.id}`}>
                          <Button variant="ghost" size="sm">
                            View
                          </Button>
                        </Link>
                        <Button
                          variant="ghost"
                          size="sm"
                          isLoading={pendingId === candidate.id}
                          onClick={() => handleDelete(candidate.id, candidate.full_name)}
                          className="text-error hover:text-error"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
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