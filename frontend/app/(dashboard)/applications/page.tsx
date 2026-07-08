"use client";

import { FolderKanban } from "lucide-react";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { EmptyState, ErrorAlert, Spinner } from "@/components/ui/feedback";
import { useApplications } from "@/hooks/use-applications";
import { useCandidates } from "@/hooks/use-candidates";
import { useJobs } from "@/hooks/use-jobs";

const statusVariant: Record<string, "success" | "warning" | "default" | "accent" | "error"> = {
  submitted: "default",
  shortlisted: "accent",
  interviewing: "warning",
  offered: "success",
  rejected: "error",
  withdrawn: "default",
};

export default function ApplicationsPage() {
  const { data: applications, isLoading, isError } = useApplications();
  const { data: candidates } = useCandidates();
  const { data: jobs } = useJobs();

  const candidateName = new Map(candidates?.map((c) => [c.id, c.full_name]));
  const jobTitle = new Map(jobs?.map((j) => [j.id, j.title]));

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-foreground">Applications</h1>
        <p className="text-sm text-muted-foreground">Every candidate-to-job application across all jobs.</p>
      </div>

      {isLoading && (
        <div className="flex justify-center py-16">
          <Spinner />
        </div>
      )}

      {isError && <ErrorAlert message="Couldn't load applications. Check that the backend is running." />}

      {applications && applications.length === 0 && (
        <EmptyState
          icon={<FolderKanban className="h-6 w-6" />}
          title="No applications yet"
          description="Run AI ranking on a job to generate applications for matched candidates."
        />
      )}

      {applications && applications.length > 0 && (
        <Card className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-border text-xs uppercase tracking-wide text-muted">
                  <th className="px-5 py-3 font-medium">Candidate</th>
                  <th className="px-5 py-3 font-medium">Job</th>
                  <th className="px-5 py-3 font-medium">Match Score</th>
                  <th className="px-5 py-3 font-medium">Status</th>
                  <th className="px-5 py-3 font-medium">Applied</th>
                </tr>
              </thead>
              <tbody>
                {applications.map((app) => (
                  <tr key={app.id} className="border-b border-border/60 last:border-0">
                    <td className="px-5 py-3">
                      <Link href={`/candidates/${app.candidate_id}`} className="font-medium text-foreground hover:text-primary">
                        {candidateName.get(app.candidate_id) ?? "Candidate"}
                      </Link>
                    </td>
                    <td className="px-5 py-3">
                      <Link href={`/jobs/${app.job_id}`} className="text-foreground hover:text-primary">
                        {jobTitle.get(app.job_id) ?? "Job"}
                      </Link>
                    </td>
                    <td className="px-5 py-3 text-muted-foreground">
                      {app.match_score !== null ? `${Math.round(app.match_score)}%` : "—"}
                    </td>
                    <td className="px-5 py-3">
                      <Badge variant={statusVariant[app.status] ?? "default"}>{app.status}</Badge>
                    </td>
                    <td className="px-5 py-3 text-muted-foreground">
                      {new Date(app.created_at).toLocaleDateString()}
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