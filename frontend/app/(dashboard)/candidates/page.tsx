"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { CheckCircle2, FileText, UploadCloud } from "lucide-react";
import { useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ErrorAlert } from "@/components/ui/feedback";
import { Input, Label } from "@/components/ui/input";
import { useCreateCandidate, useUploadResume } from "@/hooks/use-candidates";
import { ApiError } from "@/lib/api-client";
import type { Candidate } from "@/types/candidate";
import type { Resume } from "@/types/candidate";

const schema = z.object({
  full_name: z.string().min(2, "Enter the candidate's full name"),
  email: z.string().email("Enter a valid email address"),
  phone: z.string().optional(),
});

type FormValues = z.infer<typeof schema>;

export default function AddCandidatePage() {
  const createCandidate = useCreateCandidate();
  const uploadResume = useUploadResume();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [candidate, setCandidate] = useState<Candidate | null>(null);
  const [resume, setResume] = useState<Resume | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  async function onSubmit(values: FormValues) {
    setError(null);
    try {
      const created = await createCandidate.mutateAsync(values);
      setCandidate(created);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Couldn't create the candidate. Please try again.");
    }
  }

  async function handleFile(file: File) {
    if (!candidate) return;
    if (file.type !== "application/pdf") {
      setError("Only PDF resumes are accepted.");
      return;
    }
    setError(null);
    try {
      const uploaded = await uploadResume.mutateAsync({ candidateId: candidate.id, file });
      setResume(uploaded);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Couldn't upload the resume. Please try again.");
    }
  }

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="mb-1 text-xl font-semibold text-foreground">Add Candidate</h1>
      <p className="mb-6 text-sm text-muted-foreground">
        Add a candidate, then upload their resume — it&apos;s parsed and embedded immediately.
      </p>

      {error && (
        <div className="mb-4">
          <ErrorAlert message={error} />
        </div>
      )}

      {!candidate && (
        <Card>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div>
              <Label htmlFor="full_name">Full name</Label>
              <Input id="full_name" placeholder="Asha Kumar" error={errors.full_name?.message} {...register("full_name")} />
            </div>
            <div>
              <Label htmlFor="email">Email</Label>
              <Input id="email" type="email" placeholder="asha@example.com" error={errors.email?.message} {...register("email")} />
            </div>
            <div>
              <Label htmlFor="phone">Phone (optional)</Label>
              <Input id="phone" placeholder="+91 98765 43210" {...register("phone")} />
            </div>
            <Button type="submit" className="w-full" isLoading={isSubmitting}>
              Continue to resume upload
            </Button>
          </form>
        </Card>
      )}

      {candidate && !resume && (
        <Card>
          <div className="mb-4 flex items-center gap-3 rounded-lg bg-success/10 px-3 py-2 text-sm text-success">
            <CheckCircle2 className="h-4 w-4" />
            {candidate.full_name} added
          </div>

          <div
            onDragOver={(e) => {
              e.preventDefault();
              setIsDragging(true);
            }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={(e) => {
              e.preventDefault();
              setIsDragging(false);
              const file = e.dataTransfer.files?.[0];
              if (file) handleFile(file);
            }}
            onClick={() => fileInputRef.current?.click()}
            className={`flex cursor-pointer flex-col items-center justify-center rounded-[24px] border-2 border-dashed px-6 py-12 text-center transition-colors ${
              isDragging ? "border-primary bg-primary/5" : "border-border bg-surface hover:border-primary/50"
            }`}
          >
            <UploadCloud className={`mb-3 h-8 w-8 ${isDragging ? "text-primary" : "text-muted"}`} />
            <p className="text-sm font-medium text-foreground">
              {uploadResume.isPending ? "Uploading…" : "Drop resume here or click to browse"}
            </p>
            <p className="mt-1 text-xs text-muted">PDF only, up to 10MB</p>
            <input
              ref={fileInputRef}
              type="file"
              accept="application/pdf"
              className="hidden"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) handleFile(file);
              }}
            />
          </div>
        </Card>
      )}

      {candidate && resume && (
        <Card>
          <div className="mb-4 flex items-center gap-3 rounded-lg bg-success/10 px-3 py-2 text-sm text-success">
            <CheckCircle2 className="h-4 w-4" />
            Resume uploaded and parsed
          </div>

          <div className="mb-4 flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/15 text-primary">
              <FileText className="h-5 w-5" />
            </div>
            <div>
              <p className="text-sm font-medium text-foreground">{candidate.full_name}</p>
              <p className="text-xs text-muted-foreground">
                {resume.parsed_experience_years ? `${resume.parsed_experience_years} years experience` : "Experience not detected"}
              </p>
            </div>
          </div>

          {resume.parsed_skills.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {resume.parsed_skills.map((skill) => (
                <Badge key={skill} variant="accent">
                  {skill}
                </Badge>
              ))}
            </div>
          )}

          <Button
            variant="secondary"
            className="mt-6 w-full"
            onClick={() => {
              setCandidate(null);
              setResume(null);
            }}
          >
            Add another candidate
          </Button>
        </Card>
      )}
    </div>
  );
}
