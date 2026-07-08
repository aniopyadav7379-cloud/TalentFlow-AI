"use client";

import { FileText } from "lucide-react";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { EmptyState, ErrorAlert, Spinner } from "@/components/ui/feedback";
import { useCandidates } from "@/hooks/use-candidates";
import { useResumes } from "@/hooks/use-resumes";

export default function ResumeLibraryPage() {
  const { data: resumes, isLoading, isError } = useResumes();
  const { data: candidates } = useCandidates();

  const candidateName = new Map(candidates?.map((c) => [c.id, c.full_name]));

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-foreground">Resume Library</h1>
        <p className="text-sm text-muted-foreground">Every resume uploaded, with parsed skills and experience.</p>
      </div>

      {isLoading && (
        <div className="flex justify-center py-16">
          <Spinner />
        </div>
      )}

      {isError && <ErrorAlert message="Couldn't load resumes. Check that the backend is running." />}

      {resumes && resumes.length === 0 && (
        <EmptyState
          icon={<FileText className="h-6 w-6" />}
          title="No resumes uploaded yet"
          description="Resumes appear here once uploaded from a candidate's page."
        />
      )}

      {resumes && resumes.length > 0 && (
        <Card className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-border text-xs uppercase tracking-wide text-muted">
                  <th className="px-5 py-3 font-medium">Candidate</th>
                  <th className="px-5 py-3 font-medium">Resume</th>
                  <th className="px-5 py-3 font-medium">Parsed</th>
                  <th className="px-5 py-3 font-medium">Skills</th>
                  <th className="px-5 py-3 font-medium">Uploaded</th>
                </tr>
              </thead>
              <tbody>
                {resumes.map((resume) => (
                  <tr key={resume.id} className="border-b border-border/60 last:border-0">
                    <td className="px-5 py-3">
                      <Link
                        href={`/candidates/${resume.candidate_id}`}
                        className="font-medium text-foreground hover:text-primary"
                      >
                        {candidateName.get(resume.candidate_id) ?? "Candidate"}
                      </Link>
                    </td>
                    <td className="px-5 py-3">
                      <a href={resume.file_url} target="_blank" rel="noreferrer" className="text-primary hover:underline">
                        View file
                      </a>
                    </td>
                    <td className="px-5 py-3">
                      <Badge variant={resume.parse_status === "parsed" ? "success" : "default"}>
                        {resume.parse_status}
                      </Badge>
                    </td>
                    <td className="px-5 py-3">
                      <div className="flex max-w-xs flex-wrap gap-1">
                        {resume.parsed_skills.slice(0, 4).map((skill) => (
                          <Badge key={skill} variant="accent">
                            {skill}
                          </Badge>
                        ))}
                        {resume.parsed_skills.length > 4 && (
                          <span className="text-xs text-muted-foreground">+{resume.parsed_skills.length - 4}</span>
                        )}
                      </div>
                    </td>
                    <td className="px-5 py-3 text-muted-foreground">
                      {new Date(resume.created_at).toLocaleDateString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}