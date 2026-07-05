"use client";

import { ArrowLeft, Sparkles } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";

import { JobStatusBadge } from "@/components/jobs/job-status-badge";
import { MastraAgentPanel } from "@/components/jobs/mastra-agent-panel";
import { ShortlistCard } from "@/components/jobs/shortlist-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState, ErrorAlert, Spinner } from "@/components/ui/feedback";
import { useJob, useRunShortlist } from "@/hooks/use-jobs";
import { ApiError } from "@/lib/api-client";

export default function JobDetailPage() {
  const params = useParams<{ jobId: string }>();
  const jobId = params.jobId;
  const { data: job, isLoading, isError } = useJob(jobId);
  const runShortlist = useRunShortlist(jobId);
  const [shortlistError, setShortlistError] = useState<string | null>(null);

  async function handleRunShortlist() {
    setShortlistError(null);
    try {
      await runShortlist.mutateAsync(10);
    } catch (err) {
      setShortlistError(
        err instanceof ApiError ? err.detail : "Couldn't run the shortlist pipeline. Please try again."
      );
    }
  }

  if (isLoading) {
    return (
      <div className="flex justify-center py-16">
        <Spinner />
      </div>
    );
  }

  if (isError || !job) {
    return <ErrorAlert message="Couldn't load this job." />;
  }

  return (
    <div>
      <Link
        href="/jobs"
        className="mb-4 inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to jobs
      </Link>

      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <div className="mb-2 flex items-center gap-2">
            <h1 className="text-xl font-semibold text-foreground">{job.title}</h1>
            <JobStatusBadge status={job.status} />
          </div>
          <p className="text-sm text-muted-foreground">
            {[job.department, job.location, job.employment_type].filter(Boolean).join(" · ")}
          </p>
        </div>
        <Button onClick={handleRunShortlist} isLoading={runShortlist.isPending}>
          <Sparkles className="h-4 w-4" />
          Run AI Shortlist
        </Button>
      </div>

      {job.skills.length > 0 && (
        <div className="mb-6 flex flex-wrap gap-1.5">
          {job.skills.map((skill) => (
            <Badge key={skill} variant="accent">
              {skill}
            </Badge>
          ))}
        </div>
      )}

      <Card className="mb-8">
        <h2 className="mb-2 text-sm font-semibold text-foreground">Description</h2>
        <p className="whitespace-pre-wrap text-sm text-muted-foreground">{job.description}</p>
        {job.requirements && (
          <>
            <h2 className="mb-2 mt-4 text-sm font-semibold text-foreground">Requirements</h2>
            <p className="whitespace-pre-wrap text-sm text-muted-foreground">{job.requirements}</p>
          </>
        )}
      </Card>

      <div>
        <h2 className="mb-4 text-sm font-semibold text-foreground">AI Candidate Ranking</h2>

        {shortlistError && (
          <div className="mb-4">
            <ErrorAlert message={shortlistError} />
          </div>
        )}

        {runShortlist.isPending && (
          <div className="flex flex-col items-center gap-3 py-16 text-center">
            <Spinner className="h-6 w-6" />
            <p className="text-sm text-muted-foreground">
              Ranking candidates, checking fairness guardrails, and generating interview questions…
            </p>
          </div>
        )}

        {!runShortlist.isPending && !runShortlist.data && (
          <EmptyState
            title="No shortlist yet"
            description="Run the AI shortlist to semantically rank candidates against this role and generate interview questions."
            icon={<Sparkles className="h-6 w-6" />}
          />
        )}

        {!runShortlist.isPending && runShortlist.data && runShortlist.data.length === 0 && (
          <EmptyState
            title="No matching candidates found"
            description="Upload resumes for candidates first, then run the shortlist again."
          />
        )}

        {!runShortlist.isPending && runShortlist.data && runShortlist.data.length > 0 && (
          <div className="space-y-3">
            {runShortlist.data.map((entry, index) => (
              <ShortlistCard key={entry.application_id} entry={entry} rank={index + 1} />
            ))}
          </div>
        )}
      </div>

      <MastraAgentPanel job={job} />
    </div>
  );
}
