"use client";

import { Plus, Search } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";

import { JobCard } from "@/components/jobs/job-card";
import { Button } from "@/components/ui/button";
import { EmptyState, ErrorAlert, Spinner } from "@/components/ui/feedback";
import { Input } from "@/components/ui/input";
import { useJobs } from "@/hooks/use-jobs";

export default function JobsDashboardPage() {
  const { data: jobs, isLoading, isError } = useJobs();
  const [search, setSearch] = useState("");

  const filteredJobs = useMemo(() => {
    if (!jobs) return [];
    const query = search.trim().toLowerCase();
    if (!query) return jobs;
    return jobs.filter(
      (job) =>
        job.title.toLowerCase().includes(query) ||
        job.skills.some((skill) => skill.toLowerCase().includes(query))
    );
  }, [jobs, search]);

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-foreground">Jobs</h1>
          <p className="text-sm text-muted-foreground">Manage open roles and review AI-ranked candidates.</p>
        </div>
        <Link href="/jobs/create">
          <Button>
            <Plus className="h-4 w-4" />
            Create Job
          </Button>
        </Link>
      </div>

      <div className="mb-6 max-w-sm">
        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
          <Input
            placeholder="Search by title or skill…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>
      </div>

      {isLoading && (
        <div className="flex justify-center py-16">
          <Spinner />
        </div>
      )}

      {isError && <ErrorAlert message="Couldn't load jobs. Check that the backend is running and try again." />}

      {!isLoading && !isError && filteredJobs.length === 0 && (
        <EmptyState
          title={search ? "No jobs match your search" : "No jobs yet"}
          description={search ? "Try a different title or skill." : "Create your first job to start ranking candidates."}
          action={
            !search && (
              <Link href="/jobs/create">
                <Button variant="secondary">
                  <Plus className="h-4 w-4" />
                  Create Job
                </Button>
              </Link>
            )
          }
        />
      )}

      {!isLoading && !isError && filteredJobs.length > 0 && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filteredJobs.map((job) => (
            <JobCard key={job.id} job={job} />
          ))}
        </div>
      )}
    </div>
  );
}
