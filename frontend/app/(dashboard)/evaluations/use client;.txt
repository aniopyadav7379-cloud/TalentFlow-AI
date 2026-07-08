"use client";

import { ShieldCheck } from "lucide-react";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { EmptyState, ErrorAlert, Spinner } from "@/components/ui/feedback";
import { useApplications } from "@/hooks/use-applications";
import { useCandidates } from "@/hooks/use-candidates";
import { useEvaluations } from "@/hooks/use-evaluations";
import { useJobs } from "@/hooks/use-jobs";

export default function EvaluationsPage() {
  const { data: evaluations, isLoading, isError } = useEvaluations();
  const { data: applications } = useApplications();
  const { data: candidates } = useCandidates();
  const { data: jobs } = useJobs();

  const applicationById = new Map(applications?.map((a) => [a.id, a]));
  const candidateName = new Map(candidates?.map((c) => [c.id, c.full_name]));
  const jobTitle = new Map(jobs?.map((j) => [j.id, j.title]));

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-foreground">AI Evaluations</h1>
        <p className="text-sm text-muted-foreground">
          Enkrypt AI guardrail results — fairness and bias checks on AI-driven decisions.
        </p>
      </div>

      {isLoading && (
        <div className="flex justify-center py-16">
          <Spinner />
        </div>
      )}

      {isError && <ErrorAlert message="Couldn't load evaluations. Check that the backend is running." />}

      {evaluations && evaluations.length === 0 && (
        <EmptyState
          icon={<ShieldCheck className="h-6 w-6" />}
          title="No evaluations yet"
          description="Guardrail evaluations appear here once AI ranking or interviews run."
        />
      )}

      {evaluations && evaluations.length > 0 && (
        <Card className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-border text-xs uppercase tracking-wide text-muted">
                  <th className="px-5 py-3 font-medium">Candidate</th>
                  <th className="px-5 py-3 font-medium">Job</th>
                  <th className="px-5 py-3 font-medium">Fairness Score</th>
                  <th className="px-5 py-3 font-medium">Recommendation</th>
                  <th className="px-5 py-3 font-medium">Bias Check</th>
                </tr>
              </thead>
              <tbody>
                {evaluations.map((evaluation) => {
                  const application = applicationById.get(evaluation.application_id);
                  return (
                    <tr key={evaluation.id} className="border-b border-border/60 last:border-0">
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
                        {evaluation.fairness_score !== null ? `${Math.round(evaluation.fairness_score * 100)}%` : "—"}
                      </td>
                      <td className="px-5 py-3 text-muted-foreground">
                        {evaluation.final_recommendation ?? "—"}
                      </td>
                      <td className="px-5 py-3">
                        {evaluation.passed_guardrails ? (
                          <Badge variant="success">Passed</Badge>
                        ) : (
                          <Badge variant="error">{evaluation.bias_flags.length > 0 ? evaluation.bias_flags.join(", ") : "Flagged"}</Badge>
                        )}
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