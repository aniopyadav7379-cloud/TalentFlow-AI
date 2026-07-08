"use client";

import { FileText, Mail, Phone, Trash2 } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorAlert, Spinner } from "@/components/ui/feedback";
import { useCandidateDetail } from "@/hooks/use-candidate-detail";
import { useDeleteCandidate } from "@/hooks/use-candidates";
import { ApiError } from "@/lib/api-client";

const applicationStatusVariant: Record<string, "success" | "warning" | "default" | "accent" | "error"> = {
  submitted: "default",
  shortlisted: "accent",
  interviewing: "warning",
  offered: "success",
  rejected: "error",
  withdrawn: "default",
};

export default function CandidateDetailPage() {
  const params = useParams<{ candidateId: string }>();
  const router = useRouter();
  const { candidate, resumes, applicationRows, isLoading, isError } = useCandidateDetail(params.candidateId);
  const deleteCandidate = useDeleteCandidate();
  const [error, setError] = useState<string | null>(null);

  async function handleDelete() {
    if (!candidate) return;
    if (!window.confirm(`Delete ${candidate.full_name}? This also removes their resumes and applications.`)) return;
    setError(null);
    try {
      await deleteCandidate.mutateAsync(candidate.id);
      router.push("/candidates");
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Couldn't delete this candidate. Please try again.");
    }
  }

  if (isLoading) {
    return (
      <div className="flex justify-center py-16">
        <Spinner />
      </div>
    );
  }

  if (isError || !candidate) {
    return <ErrorAlert message="Couldn't load this candidate." />;
  }

  return (
    <div className="mx-auto max-w-3xl">
      <Link href="/candidates" className="mb-4 inline-block text-sm text-muted-foreground hover:text-foreground">
        ← Back to candidates
      </Link>

      {error && (
        <div className="mb-4">
          <ErrorAlert message={error} />
        </div>
      )}

      <div className="mb-6 flex items-start justify-between">
        <div>
          <h1 className="text-xl font-semibold text-foreground">{candidate.full_name}</h1>
          <div className="mt-2 flex flex-wrap items-center gap-4 text-sm text-muted-foreground">
            <span className="flex items-center gap-1.5">
              <Mail className="h-3.5 w-3.5" />
              {candidate.email}
            </span>
            {candidate.phone && (
              <span className="flex items-center gap-1.5">
                <Phone className="h-3.5 w-3.5" />
                {candidate.phone}
              </span>
            )}
          </div>
        </div>
        <Button variant="destructive" size="sm" isLoading={deleteCandidate.isPending} onClick={handleDelete}>
          <Trash2 className="h-4 w-4" />
          Delete Candidate
        </Button>
      </div>

      <Card className="mb-6">
        <CardHeader>
          <CardTitle>Resumes</CardTitle>
        </CardHeader>
        {resumes.length === 0 ? (
          <p className="text-sm text-muted-foreground">No resume uploaded yet.</p>
        ) : (
          <div className="space-y-4">
            {resumes.map((resume) => (
              <div key={resume.id} className="rounded-lg border border-border p-4">
                <div className="mb-2 flex items-center justify-between">
                  <a
                    href={resume.file_url}
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-center gap-2 text-sm font-medium text-primary hover:underline"
                  >
                    <FileText className="h-4 w-4" />
                    View resume
                  </a>
                  <Badge variant={resume.parse_status === "parsed" ? "success" : "default"}>
                    {resume.parse_status}
                  </Badge>
                </div>
                <p className="mb-2 text-xs text-muted-foreground">
                  {resume.parsed_experience_years !== null
                    ? `${resume.parsed_experience_years} years experience`
                    : "Experience not detected"}
                </p>
                {resume.parsed_skills.length > 0 && (
                  <div className="flex flex-wrap gap-1.5">
                    {resume.parsed_skills.map((skill) => (
                      <Badge key={skill} variant="accent">
                        {skill}
                      </Badge>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Matched Jobs & Interview History</CardTitle>
        </CardHeader>
        {applicationRows.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Not applied or matched to any job yet — run AI ranking on a job to match this candidate.
          </p>
        ) : (
          <div className="space-y-3">
            {applicationRows.map(({ application, job, interview }) => (
              <div key={application.id} className="rounded-lg border border-border p-4">
                <div className="mb-2 flex items-center justify-between">
                  <Link
                    href={job ? `/jobs/${job.id}` : "#"}
                    className="font-medium text-foreground hover:text-primary"
                  >
                    {job?.title ?? "Job"}
                  </Link>
                  <Badge variant={applicationStatusVariant[application.status] ?? "default"}>
                    {application.status}
                  </Badge>
                </div>
                <div className="flex flex-wrap gap-4 text-xs text-muted-foreground">
                  <span>
                    AI Match Score:{" "}
                    <span className="font-medium text-foreground">
                      {application.match_score !== null ? `${Math.round(application.match_score)}%` : "Not ranked"}
                    </span>
                  </span>
                  {interview && (
                    <span>
                      Interview:{" "}
                      <span className="font-medium text-foreground">
                        {interview.status}
                        {interview.overall_score !== null ? ` · ${Math.round(interview.overall_score)}/100` : ""}
                      </span>
                    </span>
                  )}
                </div>
                {application.match_rationale && (
                  <p className="mt-2 text-xs text-muted-foreground">{application.match_rationale}</p>
                )}
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}