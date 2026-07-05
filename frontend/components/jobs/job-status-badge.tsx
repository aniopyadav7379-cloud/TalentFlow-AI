import { Badge } from "@/components/ui/badge";
import type { JobStatus } from "@/types/job";

const statusConfig: Record<JobStatus, { label: string; variant: "default" | "success" | "warning" | "info" }> = {
  draft: { label: "Draft", variant: "default" },
  open: { label: "Open", variant: "success" },
  closed: { label: "Closed", variant: "warning" },
  archived: { label: "Archived", variant: "default" },
};

export function JobStatusBadge({ status }: { status: JobStatus }) {
  const config = statusConfig[status];
  return <Badge variant={config.variant}>{config.label}</Badge>;
}
