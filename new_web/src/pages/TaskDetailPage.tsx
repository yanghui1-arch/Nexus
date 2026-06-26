import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { ArrowLeft, Loader2 } from 'lucide-react';
import { useAppLayout } from '@/components/layout/AppLayout';
import { Button } from '@/components/ui/button';
import { getTask } from '@/api/tasks';
import type { ApiTask } from '@/api/types';
import { STATUS_META, timeAgo } from '@/lib/workspace-task-view';

export default function TaskDetailPage() {
  const { taskId } = useParams<{ taskId: string }>();
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [task, setTask] = useState<ApiTask | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useAppLayout({
    title: t('taskDetail.title'),
    description: t('taskDetail.description'),
    topActions: (
      <Button variant="ghost" size="sm" onClick={() => navigate(-1)}>
        <ArrowLeft className="size-4" />
        Back
      </Button>
    ),
  });

  useEffect(() => {
    if (!taskId) return;

    setIsLoading(true);
    getTask(taskId)
      .then(data => {
        setTask(data);
        setError(null);
      })
      .catch(err => {
        setError(err instanceof Error ? err.message : t('taskDetail.failedToLoad'));
      })
      .finally(() => setIsLoading(false));
  }, [taskId, t]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="flex items-center gap-2 text-sm text-gray-500">
          <Loader2 className="size-4 animate-spin" />
          {t('taskDetail.loadingDescription')}
        </div>
      </div>
    );
  }

  if (error || !task) {
    return (
      <div className="rounded-2xl border border-red-200 bg-red-50 p-6">
        <p className="text-sm text-red-600">{error ?? t('taskDetail.notFoundDescription', { taskId })}</p>
      </div>
    );
  }

  const statusMeta = STATUS_META[task.status];
  const StatusIcon = statusMeta.icon;

  return (
    <div className="space-y-6">
      <div className="rounded-2xl border border-gray-200/60 bg-white p-6">
        <div className="flex items-start gap-4">
          <div className="flex size-10 items-center justify-center rounded-xl bg-gray-100">
            <StatusIcon className="size-5 text-gray-600" />
          </div>
          <div className="min-w-0 flex-1">
            <h2 className="text-lg font-bold text-[hsl(0,0%,8%)]">{task.question}</h2>
            <div className="mt-2 flex flex-wrap gap-2">
              <span className="inline-flex items-center gap-1 rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-medium text-gray-700">
                {t(`status.${task.status}`)}
              </span>
              <span className="inline-flex items-center gap-1 rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-medium text-gray-700">
                {task.agent}
              </span>
              {task.repo ? (
                <span className="inline-flex items-center gap-1 rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-medium text-gray-700">
                  {task.repo}
                </span>
              ) : null}
            </div>
          </div>
        </div>

        <div className="mt-6 grid grid-cols-2 gap-4 border-t border-gray-100 pt-4 sm:grid-cols-4">
          <div>
            <p className="text-xs text-gray-400">{t('taskDetail.created')}</p>
            <p className="mt-0.5 text-sm font-medium text-[hsl(0,0%,8%)]">{timeAgo(task.created_at)}</p>
          </div>
          <div>
            <p className="text-xs text-gray-400">{t('taskDetail.updated')}</p>
            <p className="mt-0.5 text-sm font-medium text-[hsl(0,0%,8%)]">{timeAgo(task.updated_at)}</p>
          </div>
          <div>
            <p className="text-xs text-gray-400">{t('taskDetail.agent')}</p>
            <p className="mt-0.5 text-sm font-medium text-[hsl(0,0%,8%)]">{task.agent}</p>
          </div>
          <div>
            <p className="text-xs text-gray-400">{t('taskDetail.type')}</p>
            <p className="mt-0.5 text-sm font-medium text-[hsl(0,0%,8%)]">{task.category}</p>
          </div>
        </div>

        {task.error ? (
          <div className="mt-4 rounded-xl border border-red-200 bg-red-50 p-4">
            <p className="text-xs font-medium text-red-600">{t('taskDetail.result')}</p>
            <p className="mt-1 text-sm text-red-700">{task.error}</p>
          </div>
        ) : null}

        {task.result ? (
          <div className="mt-4 rounded-xl border border-green-200 bg-green-50 p-4">
            <p className="text-xs font-medium text-green-600">{t('taskDetail.result')}</p>
            <p className="mt-1 text-sm text-green-700">{task.result}</p>
          </div>
        ) : null}
      </div>
    </div>
  );
}
