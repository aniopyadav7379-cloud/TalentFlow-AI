"use client";

import { Mic } from "lucide-react";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { EmptyState, ErrorAlert, Spinner } from "@/components/ui/feedback";
import { useApplications } from "@/hooks/use-applications";
import { useCandidates } from "@/hooks/use-candidates";
import { useInterviews } from "@/hooks/use-interviews";
import { useJobs } from "@/hooks/use-jobs";

const statusVariant: Record<string, "success" | "warning" | "default" | "accent" | "error"> = {
  pending: "default",
  scheduled: "accent",
  in_progress: "warning",
  completed: "success",
  cancelled: "error",
};

export default function InterviewsPage() {
  const { data: interviews, isLoading, isError } = useInterviews();
  const { data: applications } = useApplications();
  const { data: candidates } = useCandidates();
  const { data: jobs } = useJobs();

  const applicationById = new Map(applications?.map((a) => [a.id, a]));
  const candidateName = new Map(candidates?.map((c) => [c.id, c.full_name]));
  const jobTitle = new Map(jobs?.map((j) => [j.id, j.title]));

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-foreground">Interviews</h1>
        <p className="text-sm text-muted-foreground">AI-generated interviews across all candidates.</p>
      </div>

      {isLoading && (
        <div className="flex justify-center py-16">
          <Spinner />
        </div>
      )}

      {isError && <ErrorAlert message="Couldn't load interviews. Check that the backend is running." />}

      {interviews && interviews.length === 0 && (
        <EmptyState
          icon={<Mic className="h-6 w-6" />}
          title="No interviews yet"
          description="Interviews appear here once generated for a shortlisted candidate."
        />
      )}

      {interviews && interviews.length > 0 && (
        <Card className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-border text-xs uppercase tracking-wide text-muted">
                  <th className="px-5 py-3 font-medium">Candidate</th>
                  <th className="px-5 py-3 font-medium">Job</th>
                  <th className="px-5 py-3 font-medium">Score</th>
                  <th className="px-5 py-3 font-medium">Status</th>
                  <th className="px-5 py-3 font-medium">Created</th>
                  <th className="px-5 py-3 font-medium text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {interviews.map((interview) => {
                  const application = applicationById.get(interview.application_id);
                  return (
                    <tr key={interview.id} className="border-b border-border/60 last:border-0">
                      <td className="px-5 py-3">
                        {application ? (
                          <Link
                            href={`/candidates/${application.candidate_id}`}
                            className="font-medium text-foreground hover:text-primary"
                          >
                            {candidateName.get(application.candidate_id) ?? "Candidate"}
                          </Link>
                        ) : (
                          <span className="text-muted-foreground">—</span>
                        )}
                      </td>
                      <td className="px-5 py-3">
                        {application ? (
                          <Link href={`/jobs/${application.job_id}`} className="text-foreground hover:text-primary">
                            {jobTitle.get(application.job_id) ?? "Job"}
                          </Link>
                        ) : (
                          <span className="text-muted-foreground">—</span>
                        )}
                      </td>
                      <td className="px-5 py-3 text-muted-foreground">
                        {interview.overall_score !== null ? `${Math.round(interview.overall_score)}/100` : "—"}
                      </td>
                      <td className="px-5 py-3">
                        <Badge variant={statusVariant[interview.status] ?? "default"}>{interview.status}</Badge>
                      </td>
                      <td className="px-5 py-3 text-muted-foreground">
                        {new Date(interview.created_at).toLocaleDateString()}
                      </td>
                      <td className="px-5 py-3 text-right">
                        <Link
                          href={`/interviews/${interview.application_id}`}
                          className="font-medium text-primary hover:underline"
                        >
                          {interview.overall_score !== null ? "View Evaluation" : "Record Responses"}
                        </Link>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}