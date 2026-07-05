import { Briefcase, MapPin } from "lucide-react";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { JobStatusBadge } from "@/components/jobs/job-status-badge";
import type { Job } from "@/types/job";

export function JobCard({ job }: { job: Job }) {
  return (
    <Link href={`/jobs/${job.id}`}>
      <Card interactive className="h-full">
        <div className="mb-3 flex items-start justify-between gap-2">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/15 text-primary">
            <Briefcase className="h-5 w-5" />
          </div>
          <JobStatusBadge status={job.status} />
        </div>

        <h3 className="mb-1 text-sm font-semibold text-foreground">{job.title}</h3>
        {job.department && <p className="mb-3 text-xs text-muted-foreground">{job.department}</p>}

        {job.location && (
          <div className="mb-3 flex items-center gap-1.5 text-xs text-muted">
            <MapPin className="h-3.5 w-3.5" />
            {job.location}
          </div>
        )}

        {job.skills.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {job.skills.slice(0, 3).map((skill) => (
              <Badge key={skill} variant="default">
                {skill}
              </Badge>
            ))}
            {job.skills.length > 3 && <Badge variant="default">+{job.skills.length - 3}</Badge>}
          </div>
        )}
      </Card>
    </Link>
  );
}
