import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { getErrorDetail } from '@/api/client';
import { getTaskReviewSummary } from '@/api/tasks';
import { DashboardShell } from '@/components/layout/DashboardShell';
import { TaskBoardColumn } from './components/TaskBoardColumn';
import { TaskBoardRepoSelect } from './components/TaskBoardRepoSelect';
import { useTaskBoardData } from './hooks/useTaskBoardData';
import { TASK_BOARD_STATUS_ORDER } from './utils';

export default function TaskBoardPage() {
  const navigate = useNavigate();
  const [activeReviewTaskId, setActiveReviewTaskId] = useState<string | null>(null);
  const { groupedTasks, repoOptions, repoFilter, setRepoFilter, isLoading } =
    useTaskBoardData();

  const openReview = async (taskId: string) => {
    setActiveReviewTaskId(taskId);
    try {
      const summary = await getTaskReviewSummary(taskId);
      const readyForReviewVirtualPrs = summary.virtual_prs.filter(
        virtualPr => virtualPr.status === 'ready_for_review',
      );
      const targetVirtualPr =
        readyForReviewVirtualPrs.length === 1
          ? readyForReviewVirtualPrs[0]
          : summary.virtual_prs.length === 1
            ? summary.virtual_prs[0]
            : null;

      navigate(
        targetVirtualPr
          ? `/workspace/code-review/nexus/tasks/${taskId}/pull-requests/${targetVirtualPr.id}`
          : `/workspace/code-review/nexus/tasks/${taskId}`,
      );
    } catch (error) {
      toast.error('Failed to open review', {
        description: getErrorDetail(error, 'Unable to load the review target.'),
      });
    } finally {
      setActiveReviewTaskId(null);
    }
  };

  return (
    <DashboardShell
      title="Task Board"
      description="Live task board grouped by backend task status."
    >
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
                activeReviewTaskId={activeReviewTaskId}
                onOpenReview={taskId => {
                  void openReview(taskId);
                }}
              />
            ))}
          </div>
        </div>
      </section>
    </DashboardShell>
  );
}
