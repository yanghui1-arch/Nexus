import type { Project } from '@/types/agent';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';

type TaskCounts = {
  running: number;
  waiting_for_review: number;
  merged: number;
  closed: number;
  fail: number;
};

type OverviewSummaryCardsProps = {
  project: Project | null;
  projectCount: number;
  counts: TaskCounts;
  taskTotal: number;
  selectedAgentName: string | null;
};

export function OverviewSummaryCards({
  project,
  projectCount,
  counts,
  taskTotal,
  selectedAgentName,
}: OverviewSummaryCardsProps) {
  const scopeRepo = project?.repo ?? `${projectCount} projects`;

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <CardContent className="pt-6">
          <div className="flex flex-wrap items-center gap-4 text-sm text-muted-foreground">
            <span>{scopeRepo}</span>
            <span>{taskTotal} tasks visible</span>
            <span>
              Scope: {selectedAgentName ? selectedAgentName : 'All agents'}
            </span>
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <Card>
          <CardHeader>
            <CardDescription>Running</CardDescription>
            <CardTitle className="text-2xl">{counts.running}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader>
            <CardDescription>Waiting for Review</CardDescription>
            <CardTitle className="text-2xl">{counts.waiting_for_review}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader>
            <CardDescription>Merged</CardDescription>
            <CardTitle className="text-2xl">{counts.merged}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader>
            <CardDescription>Closed</CardDescription>
            <CardTitle className="text-2xl">{counts.closed}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader>
            <CardDescription>Failed</CardDescription>
            <CardTitle className="text-2xl">{counts.fail}</CardTitle>
          </CardHeader>
        </Card>
      </div>
    </div>
  );
}
