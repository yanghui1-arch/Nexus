import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useAppLayout } from '@/components/layout/AppLayout';
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
    <div className="min-w-0 space-y-6">
      <div className="flex items-center gap-3">
        <RepoSelect
          repoOptions={repoOptions}
          value={repoFilter}
          onChange={setRepoFilter}
        />
      </div>

      <StatusCards groupedTasks={groupedTasks} isLoading={isLoading} />

      <div className="grid min-w-0 grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1fr)_320px]">
        <div className="min-w-0 space-y-6">
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

        <div className="relative h-[620px] min-w-0 overflow-hidden xl:h-auto">
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
