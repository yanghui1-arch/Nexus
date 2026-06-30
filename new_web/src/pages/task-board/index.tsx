import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Plus, Settings } from 'lucide-react';
import { useAppLayout } from '@/components/layout/AppLayout';
import { Button } from '@/components/ui/button';
import { RepoSelect } from './components/RepoSelect';
import { StatusCards } from './components/StatusCards';
import { WorkflowTable } from './components/WorkflowTable';
import { TaskThroughputChart } from './components/TaskThroughputChart';
import { TopRepositoriesChart } from './components/TopRepositoriesChart';
import { ActivityFeed } from './components/ActivityFeed';
import { useTaskBoardData } from './hooks/useTaskBoardData';
import {
  deriveTaskBoardAgentOptions,
  filterTaskBoardTasks,
  groupTaskBoardTasks,
  type TaskBoardAgentFilter,
  type TaskBoardStatusFilter,
  type TaskBoardTab,
} from './utils';

export default function TaskBoardPage() {
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState<TaskBoardTab>('allTasks');
  const [isFilterOpen, setIsFilterOpen] = useState(false);
  const [statusFilter, setStatusFilter] = useState<TaskBoardStatusFilter>('all');
  const [agentFilter, setAgentFilter] = useState<TaskBoardAgentFilter>('all');

  useAppLayout({
    title: t('taskBoard.title'),
    description: t('taskBoard.description'),
    topActions: (
      <div className="flex items-center gap-2">
        <Button asChild variant="ghost" size="icon" className="h-9 w-9 rounded-lg border border-gray-200 bg-white text-gray-500 hover:bg-gray-50">
          <Link to="/workspace-settings" aria-label={t('nav.workspaces')}>
            <Settings className="size-4" />
          </Link>
        </Button>
        <Button asChild className="h-9 rounded-lg bg-[hsl(0,0%,8%)] text-white hover:bg-[hsl(0,0%,20%)] shadow-sm">
          <Link to="/publish-task">
            <Plus className="size-4" />
            {t('common.createTask')}
          </Link>
        </Button>
      </div>
    ),
  });

  const { groupedTasks, visibleTasks, repoOptions, repoFilter, setRepoFilter, isLoading } =
    useTaskBoardData();
  const workflowAgentOptions = useMemo(
    () => deriveTaskBoardAgentOptions(visibleTasks),
    [visibleTasks],
  );
  const filteredWorkflowTasks = useMemo(
    () =>
      filterTaskBoardTasks(visibleTasks, {
        tab: activeTab,
        status: statusFilter,
        agent: agentFilter,
      }),
    [activeTab, agentFilter, statusFilter, visibleTasks],
  );
  const workflowGroupedTasks = useMemo(
    () => groupTaskBoardTasks(filteredWorkflowTasks),
    [filteredWorkflowTasks],
  );

  useEffect(() => {
    if (agentFilter !== 'all' && !workflowAgentOptions.includes(agentFilter)) {
      setAgentFilter('all');
    }
  }, [agentFilter, workflowAgentOptions]);

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <RepoSelect
          repoOptions={repoOptions}
          value={repoFilter}
          onChange={setRepoFilter}
        />
      </div>

      <StatusCards groupedTasks={groupedTasks} isLoading={isLoading} />

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[1fr_320px]">
        <div className="space-y-6">
          <WorkflowTable
            groupedTasks={workflowGroupedTasks}
            activeTab={activeTab}
            onTabChange={setActiveTab}
            isFilterOpen={isFilterOpen}
            onFilterOpenChange={setIsFilterOpen}
            statusFilter={statusFilter}
            onStatusFilterChange={setStatusFilter}
            agentFilter={agentFilter}
            onAgentFilterChange={setAgentFilter}
            agentOptions={workflowAgentOptions}
            onClearFilters={() => {
              setStatusFilter('all');
              setAgentFilter('all');
            }}
          />

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <TaskThroughputChart />
            <TopRepositoriesChart />
          </div>
        </div>

        <div className="relative h-[620px] xl:h-auto">
          <ActivityFeed
            tasks={visibleTasks}
            isLoading={isLoading}
            className="absolute inset-0"
          />
        </div>
      </div>
    </div>
  );
}
