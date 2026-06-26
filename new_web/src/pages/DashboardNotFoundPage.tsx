import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';

export function DashboardNotFoundPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();

  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center text-center">
      <p className="text-sm font-medium text-[hsl(80,85%,55%)]">{t('notFound.eyebrow')}</p>
      <h1 className="mt-2 text-3xl font-bold tracking-tight text-[hsl(0,0%,8%)]">{t('notFound.heading')}</h1>
      <p className="mt-3 max-w-md text-sm text-gray-500">{t('notFound.body')}</p>
      <div className="mt-6 flex gap-3">
        <Button onClick={() => navigate('/task-board')} className="rounded-lg bg-[hsl(0,0%,8%)] text-white hover:bg-[hsl(0,0%,20%)]">
          {t('notFound.taskBoardAction')}
        </Button>
        <Button variant="outline" onClick={() => navigate(-1)}>
          {t('notFound.backAction')}
        </Button>
      </div>
    </div>
  );
}
