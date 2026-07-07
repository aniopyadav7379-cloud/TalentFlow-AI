"use client";

import { Briefcase, FolderOpen, Sparkles, Users } from "lucide-react";
import Link from "next/link";

import { StatCard } from "@/components/dashboard/stat-card";
import { Badge } from "@/components/ui/badge";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorAlert, Spinner } from "@/components/ui/feedback";
import { useDashboardStats } from "@/hooks/use-dashboard-stats";

const statusVariant: Record<string, "success" | "warning" | "default" | "accent"> = {
  open: "success",
  draft: "warning",
  closed: "default",
  archived: "default",
};

export default function DashboardPage() {
  const { data, isLoading, isError } = useDashboardStats();

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-foreground">Dashboard</h1>
        <p className="text-sm text-muted-foreground">A quick overview of hiring activity across your jobs.</p>
      </div>

      {isLoading && (
        <div className="flex justify-center py-16">
          <Spinner />
        </div>
      )}

      {isError && <ErrorAlert message="Couldn't load dashboard data. Check that the backend is running." />}

      {data && (
        <>
          <div className="mb-8 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard label="Total Jobs" value={data.totalJobs} icon={Briefcase} accent="primary" delay={0} />
            <StatCard
              label="Open Jobs"
              value={data.openJobs}
              icon={FolderOpen}
              accent="success"
              caption={`${data.totalJobs - data.openJobs} draft/closed`}
              delay={0.05}
            />
            <StatCard
              label="Candidates Applied"
              value={data.candidatesApplied}
              icon={Users}
              accent="accent"
              caption="Unique candidates across all applications"
              delay={0.1}
            />
            <StatCard
              label="AI Ranked"
              value={data.aiRanked}
              icon={Sparkles}
              accent="warning"
              caption={`${data.totalApplications} total applications`}
              delay={0.15}
            />
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Recent Jobs</CardTitle>
              <Link href="/jobs" className="text-sm font-medium text-primary hover:underline">
                View all
              </Link>
            </CardHeader>

            {data.jobs.length === 0 ? (
              <p className="py-8 text-center text-sm text-muted-foreground">
                No jobs yet — create your first job to get started.
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead>
                    <tr className="border-b border-border text-xs uppercase tracking-wide text-muted">
                      <th className="pb-2 pr-4 font-medium">Job Title</th>
                      <th className="pb-2 pr-4 font-medium">Status</th>
                      <th className="pb-2 pr-4 font-medium">Location</th>
                      <th className="pb-2 font-medium">Created</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.jobs.slice(0, 8).map((job) => (
                      <tr key={job.id} className="border-b border-border/60 last:border-0">
                        <td className="py-3 pr-4">
                          <Link href={`/jobs/${job.id}`} className="font-medium text-foreground hover:text-primary">
                            {job.title}
                          </Link>
                        </td>
                        <td className="py-3 pr-4">
                          <Badge variant={statusVariant[job.status] ?? "default"}>{job.status}</Badge>
                        </td>
                        <td className="py-3 pr-4 text-muted-foreground">{job.location ?? "—"}</td>
                        <td className="py-3 text-muted-foreground">
                          {new Date(job.created_at).toLocaleDateString()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </>
      )}
    </div>
  );
}