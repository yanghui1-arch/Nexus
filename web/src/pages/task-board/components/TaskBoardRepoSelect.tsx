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
  return (
    <div className="max-w-sm">
      <Select
        aria-label="Select repository"
        value={value}
        onChange={event => onChange(event.target.value)}
      >
        {repoOptions.map(repo => (
          <option key={repo} value={repo}>
            {repo}
          </option>
        ))}
      </Select>
    </div>
  );
}
