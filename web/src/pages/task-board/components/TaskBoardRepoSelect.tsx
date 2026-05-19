import { useTranslation } from 'react-i18next';
import { Select } from '@/components/ui/select';

type TaskBoardRepoSelectProps = {
  repoOptions: string[];
  value: string;
  onChange: (repo: string) => void;
};

export function TaskBoardRepoSelect({
  repoOptions,
  value,
  onChange,
}: TaskBoardRepoSelectProps) {
  const { t } = useTranslation();

  return (
    <div className="max-w-sm">
      <Select
        aria-label={t('taskBoard.selectRepository')}
        value={value}
        onChange={event => onChange(event.target.value)}
      >
        {repoOptions.map(repo => (
          <option key={repo} value={repo}>
            {repo === 'All repositories' ? t('taskBoard.allRepositories') : repo}
          </option>
        ))}
      </Select>
    </div>
  );
}
