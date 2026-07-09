"use client";

import { CheckCircle2, Mic, Send } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorAlert, Spinner } from "@/components/ui/feedback";
import { ScoreRing } from "@/components/ui/score-ring";
import { useApplication, useApplicationInterview, useSubmitInterviewResponses } from "@/hooks/use-applications";
import { useCandidates } from "@/hooks/use-candidates";
import { useJobs } from "@/hooks/use-jobs";
import { ApiError } from "@/lib/api-client";
import type { ScoreBreakdown } from "@/types/application";

const categoryVariant: Record<string, "default" | "accent" | "warning" | "success"> = {
  technical: "accent",
  behavioral: "success",
  system_design: "warning",
  problem_solving: "accent",
  culture_fit: "default",
};

const breakdownLabels: Record<keyof ScoreBreakdown, string> = {
  technical: "Technical",
  communication: "Communication",
  problem_solving: "Problem Solving",
  confidence: "Confidence",
  leadership: "Leadership",
};

export default function InterviewResponsePage() {
  const params = useParams<{ applicationId: string }>();
  const applicationId = params.applicationId;

  const { data: application } = useApplication(applicationId);
  const { data: interview, isLoading, isError } = useApplicationInterview(applicationId);
  const { data: candidates } = useCandidates();
  const { data: jobs } = useJobs();
  const submitResponses = useSubmitInterviewResponses(applicationId);

  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [submitError, setSubmitError] = useState<string | null>(null);

  const candidateName = candidates?.find((c) => c.id === application?.candidate_id)?.full_name;
  const jobTitle = jobs?.find((j) => j.id === application?.job_id)?.title;

  const hasBeenEvaluated = interview && interview.overall_score !== null;

  async function handleSubmit() {
    if (!interview) return;
    const unanswered = interview.questions.filter((q) => !answers[q.id]?.trim());
    if (unanswered.length > 0) {
      setSubmitError(`Please fill in an answer for all ${interview.questions.length} questions before submitting.`);
      return;
    }
    setSubmitError(null);
    try {
      await submitResponses.mutateAsync(
        interview.questions.map((q) => ({
          question_id: q.id,
          question: q.question,
          answer: answers[q.id],
        }))
      );
    } catch (err) {
      setSubmitError(err instanceof ApiError ? err.detail : "Couldn't submit responses. Please try again.");
    }
  }

  if (isLoading) {
    return (
      <div className="flex justify-center py-16">
        <Spinner />
      </div>
    );
  }

  if (isError || !interview) {
    return <ErrorAlert message="No interview has been generated for this application yet." />;
  }

  return (
    <div className="mx-auto max-w-3xl">
      <Link href="/interviews" className="mb-4 inline-block text-sm text-muted-foreground hover:text-foreground">
        ← Back to interviews
      </Link>

      <div className="mb-6">
        <h1 className="text-xl font-semibold text-foreground">
          {candidateName ?? "Candidate"} — {jobTitle ?? "Interview"}
        </h1>
        <p className="text-sm text-muted-foreground">
          {hasBeenEvaluated
            ? "This interview has been evaluated by AI. Responses and scores below."
            : "Enter the candidate's spoken/written answers below, then submit for AI evaluation."}
        </p>
      </div>

      {/* Overall results, shown once evaluated */}
      {hasBeenEvaluated && (
        <Card className="mb-6">
          <div className="flex flex-col items-center gap-6 sm:flex-row sm:items-start">
            <ScoreRing score={interview.overall_score ?? 0} size={100} label="Overall" />
            <div className="flex-1">
              <div className="mb-3 flex flex-wrap gap-4">
                {Object.entries(interview.score_breakdown as ScoreBreakdown).map(([key, value]) => (
                  <div key={key} className="text-center">
                    <ScoreRing score={value} size={56} strokeWidth={5} />
                    <p className="mt-1 text-[11px] text-muted-foreground">
                      {breakdownLabels[key as keyof ScoreBreakdown] ?? key}
                    </p>
                  </div>
                ))}
              </div>
              {interview.ai_recommendation && (
                <div className="rounded-lg bg-surface p-3 text-sm text-muted-foreground">
                  <span className="font-medium text-foreground">AI Recommendation: </span>
                  {interview.ai_recommendation}
                </div>
              )}
            </div>
          </div>
        </Card>
      )}

      {submitError && (
        <div className="mb-4">
          <ErrorAlert message={submitError} />
        </div>
      )}

      {/* Questions + answers */}
      <Card>
        <CardHeader>
          <CardTitle>
            <span className="flex items-center gap-2">
              <Mic className="h-4 w-4" />
              Interview Questions
            </span>
          </CardTitle>
        </CardHeader>

        <div className="space-y-6">
          {interview.questions.map((q, i) => {
            const record = interview.responses.find((r) => r.question === q.question);
            return (
              <div key={q.id} className="border-b border-border pb-6 last:border-0 last:pb-0">
                <div className="mb-2 flex items-start justify-between gap-3">
                  <p className="text-sm font-medium text-foreground">
                    {i + 1}. {q.question}
                  </p>
                  <Badge variant={categoryVariant[q.category] ?? "default"}>{q.category.replace("_", " ")}</Badge>
                </div>

                {hasBeenEvaluated ? (
                  <div className="space-y-2">
                    <p className="whitespace-pre-wrap rounded-lg bg-surface p-3 text-sm text-muted-foreground">
                      {record?.answer || "(no answer recorded)"}
                    </p>
                    {record && record.score !== null && (
                      <div className="flex items-start gap-2 text-xs">
                        <Badge variant="accent">{record.score}/10</Badge>
                        {record.feedback && <p className="text-muted-foreground">{record.feedback}</p>}
                      </div>
                    )}
                  </div>
                ) : (
                  <textarea
                    value={answers[q.id] ?? ""}
                    onChange={(e) => setAnswers((prev) => ({ ...prev, [q.id]: e.target.value }))}
                    placeholder="Type or paste the candidate's answer here..."
                    rows={3}
                    className="w-full rounded-lg border border-border bg-surface p-3 text-sm text-foreground placeholder:text-muted focus:border-primary focus:outline-none"
                  />
                )}
              </div>
            );
          })}
        </div>

        {!hasBeenEvaluated && (
          <div className="mt-6 flex justify-end">
            <Button onClick={handleSubmit} isLoading={submitResponses.isPending}>
              <Send className="h-4 w-4" />
              Submit for AI Evaluation
            </Button>
          </div>
        )}

        {hasBeenEvaluated && (
          <div className="mt-6 flex items-center gap-2 text-sm text-success">
            <CheckCircle2 className="h-4 w-4" />
            Evaluation complete
          </div>
        )}
      </Card>
    </div>
  );
}