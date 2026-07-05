"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ErrorAlert } from "@/components/ui/feedback";
import { Input, Label, Textarea } from "@/components/ui/input";
import { useCreateJob } from "@/hooks/use-jobs";
import { ApiError } from "@/lib/api-client";

// Mirrors the backend's JobCreate schema (title min 2, description min 10).
const schema = z.object({
  title: z.string().min(2, "Title is required"),
  department: z.string().optional(),
  description: z.string().min(10, "Description must be at least 10 characters"),
  requirements: z.string().optional(),
  experience_level: z.string().optional(),
  location: z.string().optional(),
  employment_type: z.string().optional(),
  salary_min: z.coerce.number().min(0).optional().or(z.literal("")),
  salary_max: z.coerce.number().min(0).optional().or(z.literal("")),
});

type FormValues = z.infer<typeof schema>;

export default function CreateJobPage() {
  const router = useRouter();
  const createJob = useCreateJob();
  const [skills, setSkills] = useState<string[]>([]);
  const [skillInput, setSkillInput] = useState("");
  const [serverError, setServerError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  function addSkill() {
    const value = skillInput.trim().toLowerCase();
    if (value && !skills.includes(value)) {
      setSkills([...skills, value]);
    }
    setSkillInput("");
  }

  function removeSkill(skill: string) {
    setSkills(skills.filter((s) => s !== skill));
  }

  async function onSubmit(values: FormValues) {
    setServerError(null);
    try {
      const job = await createJob.mutateAsync({
        ...values,
        salary_min: values.salary_min === "" ? undefined : values.salary_min,
        salary_max: values.salary_max === "" ? undefined : values.salary_max,
        skills,
      });
      router.push(`/jobs/${job.id}`);
    } catch (err) {
      setServerError(err instanceof ApiError ? err.detail : "Something went wrong. Please try again.");
    }
  }

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="mb-1 text-xl font-semibold text-foreground">Create Job</h1>
      <p className="mb-6 text-sm text-muted-foreground">
        The job description and skills are embedded immediately, so this role is matchable as soon as it&apos;s created.
      </p>

      <Card>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
          {serverError && <ErrorAlert message={serverError} />}

          <div>
            <Label htmlFor="title">Job title</Label>
            <Input id="title" placeholder="Backend Engineer" error={errors.title?.message} {...register("title")} />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label htmlFor="department">Department</Label>
              <Input id="department" placeholder="Engineering" {...register("department")} />
            </div>
            <div>
              <Label htmlFor="experience_level">Experience level</Label>
              <Input id="experience_level" placeholder="Mid-Senior" {...register("experience_level")} />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label htmlFor="location">Location</Label>
              <Input id="location" placeholder="Remote" {...register("location")} />
            </div>
            <div>
              <Label htmlFor="employment_type">Employment type</Label>
              <Input id="employment_type" placeholder="Full-time" {...register("employment_type")} />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label htmlFor="salary_min">Salary min</Label>
              <Input id="salary_min" type="number" placeholder="80000" {...register("salary_min")} />
            </div>
            <div>
              <Label htmlFor="salary_max">Salary max</Label>
              <Input id="salary_max" type="number" placeholder="120000" {...register("salary_max")} />
            </div>
          </div>

          <div>
            <Label htmlFor="skills">Skills</Label>
            <div className="flex gap-2">
              <Input
                id="skills"
                placeholder="Add a skill and press Enter"
                value={skillInput}
                onChange={(e) => setSkillInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    addSkill();
                  }
                }}
              />
              <Button type="button" variant="secondary" onClick={addSkill}>
                Add
              </Button>
            </div>
            {skills.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-1.5">
                {skills.map((skill) => (
                  <Badge key={skill} variant="accent" className="gap-1">
                    {skill}
                    <button type="button" onClick={() => removeSkill(skill)} aria-label={`Remove ${skill}`}>
                      <X className="h-3 w-3" />
                    </button>
                  </Badge>
                ))}
              </div>
            )}
          </div>

          <div>
            <Label htmlFor="description">Description</Label>
            <Textarea
              id="description"
              placeholder="Describe the role, responsibilities, and what success looks like."
              error={errors.description?.message}
              {...register("description")}
            />
          </div>

          <div>
            <Label htmlFor="requirements">Requirements</Label>
            <Textarea id="requirements" placeholder="Required qualifications and experience." {...register("requirements")} />
          </div>

          <div className="flex justify-end gap-3">
            <Button type="button" variant="secondary" onClick={() => router.back()}>
              Cancel
            </Button>
            <Button type="submit" isLoading={isSubmitting}>
              Create Job
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
}
