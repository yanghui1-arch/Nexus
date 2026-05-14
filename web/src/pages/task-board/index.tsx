import { useNavigate } from 'react-router-dom';
import { AgentEntitlementEmptyState } from '@/components/entitlements/AgentEntitlementStates';
import { useAppLayout } from '@/components/layout/AppLayout';
import { TaskBoardColumn } from './components/TaskBoardColumn';
import { TaskBoardRepoSelect } from './components/TaskBoardRepoSelect';
import { useTaskBoardData } from './hooks/useTaskBoardData';
import { TASK_BOARD_STATUS_ORDER } from './utils';

export default function TaskBoardPage() {
  useAppLayout({
    title: 'Task Board',
    description: 'Live task board grouped by backend task status.',
  });

  const navigate = useNavigate();
  const { groupedTasks, repoOptions, repoFilter, setRepoFilter, isLoading, hasActiveAgents } =
    useTaskBoardData();

  const openReview = (taskId: string) => {
    navigate(`/code-review/nexus/tasks/${taskId}`);
  };

  if (!isLoading && !hasActiveAgents) {
    return <AgentEntitlementEmptyState />;
  }

  return (
    <section className="space-y-4">
      <TaskBoardRepoSelect
        repoOptions={repoOptions}
        value={repoFilter}
        onChange={setRepoFilter}
      />

      <div className="overflow-x-auto">
        <div className="grid min-w-[720px] grid-cols-4 gap-4">
          {TASK_BOARD_STATUS_ORDER.map(status => (
            <TaskBoardColumn
              key={status}
              status={status}
              tasks={groupedTasks[status]}
              isLoading={isLoading}
              onOpenReview={openReview}
            />
          ))}
        </div>
      </div>
    </section>
  );
}
