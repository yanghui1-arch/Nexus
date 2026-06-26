import { useTranslation } from 'react-i18next';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { SiGithub } from 'react-icons/si';

type RepoSelectProps = {
  repoOptions: string[];
  value: string;
  onChange: (repo: string) => void;
};

export function RepoSelect({
  repoOptions,
  value,
  onChange,
}: RepoSelectProps) {
  const { t } = useTranslation();

  return (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger className="h-10 w-[220px] border-gray-200 bg-white text-sm font-medium">
        <SiGithub className="mr-2 size-4 text-gray-400" />
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {repoOptions.map(repo => (
          <SelectItem key={repo} value={repo}>
            {repo === 'All repositories' ? t('taskBoard.allRepositories') : repo}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
