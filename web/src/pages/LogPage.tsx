import { useMemo, useState } from 'react';
import { Navigate, useParams } from 'react-router-dom';
import {
  getAgentTasks,
  getProjectTasks,
  mockProjects,
} from '@/data/mockWorkflows';
import { DashboardShell } from '@/components/layout/DashboardShell';
import { OverviewSummaryCards } from '@/components/overview/OverviewSummaryCards';
import { OverviewTaskFilters } from '@/components/overview/OverviewTaskFilters';
import { OverviewTaskList } from '@/components/overview/OverviewTaskList';
import {
  countTasks,
  filterTasks,
  type FilterTab,
} from '@/components/overview/overview-utils';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { DEFAULT_OVERVIEW_PATH } from '@/lib/dashboard-nav';

export default function LogPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null);
  const [filter, setFilter] = useState<FilterTab>('all');

  const project = useMemo(() => {
    if (!projectId) return null;
    return mockProjects.find(candidate => candidate.id === projectId) ?? null;
  }, [projectId]);

  if (!project) {
    return <Navigate to={DEFAULT_OVERVIEW_PATH} replace />;
  }

  const selectedAgent = useMemo(() => {
    if (!selectedAgentId) return null;
    return project.agents.find(agent => agent.id === selectedAgentId) ?? null;
  }, [project, selectedAgentId]);

  const baseTasks = useMemo(() => {
    if (selectedAgent) return getAgentTasks(selectedAgent);
    return getProjectTasks(project);
  }, [project, selectedAgent]);

  const counts = useMemo(() => countTasks(baseTasks), [baseTasks]);
  const filteredTasks = useMemo(
    () => filterTasks(baseTasks, filter),
    [baseTasks, filter],
  );

  return (
    <DashboardShell
      title={`Overview · ${project.name}`}
      description={project.description}
    >
      <section className="flex min-w-0 flex-col gap-6">
        <OverviewSummaryCards
          project={project}
          projectCount={mockProjects.length}
          counts={counts}
          taskTotal={baseTasks.length}
          selectedAgentName={selectedAgent?.name ?? null}
        />

        <Card>
          <CardHeader>
            <CardTitle>Agent Scope</CardTitle>
            <CardDescription>
              Narrow the feed to one agent or keep all agents.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-2">
            <Button
              type="button"
              size="sm"
              variant={selectedAgentId === null ? 'default' : 'outline'}
              onClick={() => {
                setSelectedAgentId(null);
                setFilter('all');
              }}
            >
              All agents
            </Button>
            {project.agents.map(agent => (
              <Button
                key={agent.id}
                type="button"
                size="sm"
                variant={selectedAgentId === agent.id ? 'default' : 'outline'}
                onClick={() => {
                  setSelectedAgentId(agent.id);
                  setFilter('all');
                }}
              >
                {agent.name}
              </Button>
            ))}
          </CardContent>
        </Card>

        <OverviewTaskFilters
          filter={filter}
          counts={counts}
          total={baseTasks.length}
          onChange={setFilter}
        />

        <OverviewTaskList tasks={filteredTasks} />
      </section>
    </DashboardShell>
  );
}
