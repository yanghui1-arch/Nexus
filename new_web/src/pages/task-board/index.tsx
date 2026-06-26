import { useState } from 'react';
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

export default function TaskBoardPage() {
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState('allTasks');

  useAppLayout({
    title: t('taskBoard.title'),
    description: t('taskBoard.description'),
    topActions: (
      <div className="flex items-center gap-2">
        <Button variant="ghost" size="icon" className="h-9 w-9 rounded-lg border border-gray-200 bg-white text-gray-500 hover:bg-gray-50">
          <Settings className="size-4" />
        </Button>
        <Button className="h-9 rounded-lg bg-[hsl(0,0%,8%)] text-white hover:bg-[hsl(0,0%,20%)] shadow-sm">
          <Plus className="size-4" />
          {t('common.createTask')}
        </Button>
      </div>
    ),
  });

  const { groupedTasks, repoOptions, repoFilter, setRepoFilter, isLoading } =
    useTaskBoardData();

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
            groupedTasks={groupedTasks}
            activeTab={activeTab}
            onTabChange={setActiveTab}
          />

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <TaskThroughputChart />
            <TopRepositoriesChart />
          </div>
        </div>

        <ActivityFeed />
      </div>
    </div>
  );
}
