import { useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAppLayout } from '@/components/layout/AppLayout';
import { TaskBoardColumn } from './components/TaskBoardColumn';
import { TaskBoardRepoSelect } from './components/TaskBoardRepoSelect';
import { useTaskBoardData } from './hooks/useTaskBoardData';
import { TASK_BOARD_STATUS_ORDER } from './utils';

export default function TaskBoardPage() {
  const { t } = useTranslation();
  const [searchParams] = useSearchParams();

  useAppLayout({
    title: t('taskBoard.title'),
    description: t('taskBoard.description'),
  });

  const navigate = useNavigate();
  const { groupedTasks, repoOptions, repoFilter, setRepoFilter, isLoading } =
    useTaskBoardData();
  const statusParam = searchParams.get('status');
  const visibleStatuses =
    statusParam === 'failed' ? (['failed'] as const) : TASK_BOARD_STATUS_ORDER;

  useEffect(() => {
    if (statusParam !== 'failed') {
      return;
    }

    const failedTask = groupedTasks.failed[0];
    if (failedTask?.repo && failedTask.repo !== repoFilter) {
      setRepoFilter(failedTask.repo);
    }
  }, [groupedTasks.failed, repoFilter, setRepoFilter, statusParam]);

  const openReview = (taskId: string) => {
    navigate(`/code-review/nexus/tasks/${taskId}`);
  };

  return (
    <section className="space-y-4">
      <TaskBoardRepoSelect
        repoOptions={repoOptions}
        value={repoFilter}
        onChange={setRepoFilter}
      />

      <div className="overflow-x-auto">
        <div className={statusParam === 'failed' ? 'grid min-w-[240px] grid-cols-1 gap-4' : 'grid min-w-[900px] grid-cols-5 gap-4'}>
          {visibleStatuses.map(status => (
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
