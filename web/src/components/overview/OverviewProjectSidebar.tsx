import type { Project } from '@/types/agent';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { ScrollArea } from '@/components/ui/scroll-area';
import { projectRunningCount } from './overview-utils';

type OverviewProjectSidebarProps = {
  projects: Project[];
  selectedProjectId: string | null;
  onSelectOverview: () => void;
  onSelectProject: (projectId: string) => void;
};

export function OverviewProjectSidebar({
  projects,
  selectedProjectId,
  onSelectOverview,
  onSelectProject,
}: OverviewProjectSidebarProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Overview Scope</CardTitle>
        <CardDescription>Use Overview or drill into one project.</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="flex flex-col gap-2">
          <Button
            type="button"
            variant={selectedProjectId === null ? 'default' : 'outline'}
            className="justify-start"
            onClick={onSelectOverview}
          >
            Overview
          </Button>

          <ScrollArea className="max-h-[440px] pr-2">
            <div className="flex flex-col gap-2">
              {projects.map(project => {
                const isSelected = project.id === selectedProjectId;
                const runningCount = projectRunningCount(project);

                return (
                  <Button
                    key={project.id}
                    type="button"
                    variant={isSelected ? 'default' : 'outline'}
                    className="h-auto justify-start px-3 py-2"
                    onClick={() => onSelectProject(project.id)}
                  >
                    <div className="flex w-full flex-col gap-2 text-left">
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-sm font-medium">{project.name}</span>
                        <Badge variant={runningCount > 0 ? 'default' : 'secondary'}>
                          {runningCount} active
                        </Badge>
                      </div>
                      <p className="text-xs text-muted-foreground">{project.repo}</p>
                      <p className="text-xs text-muted-foreground">
                        {project.agents.length} agents
                      </p>
                    </div>
                  </Button>
                );
              })}
            </div>
          </ScrollArea>
        </div>
      </CardContent>
    </Card>
  );
}
