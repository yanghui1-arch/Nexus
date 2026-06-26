import { useTranslation } from 'react-i18next';
import { BarChart3 } from 'lucide-react';
import { cn } from '@/lib/utils';

type TaskThroughputChartProps = {
  className?: string;
};

const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

const SERIES = [
  { key: 'completed', color: '#84cc16', labelKey: 'taskBoard.completed' },
  { key: 'inProgress', color: '#1a1a1a', labelKey: 'taskBoard.inProgress' },
  { key: 'failed', color: '#ef4444', labelKey: 'taskBoard.failed' },
  { key: 'queued', color: '#3b82f6', labelKey: 'taskBoard.queued' },
];

function generateSeriesData(): Record<string, number[]> {
  const data: Record<string, number[]> = {};
  for (const s of SERIES) {
    const values: number[] = [];
    let base = s.key === 'completed' ? 18 : s.key === 'inProgress' ? 10 : s.key === 'failed' ? 4 : 6;
    for (let i = 0; i < 7; i++) {
      values.push(Math.max(0, base + (Math.random() - 0.5) * 8));
    }
    data[s.key] = values;
  }
  return data;
}

function LinePath({ data, color, width, height }: { data: number[]; color: string; width: number; height: number }) {
  const max = Math.max(...data, 1);
  const points = data.map((value, index) => {
    const x = (index / (data.length - 1)) * width;
    const y = height - (value / max) * (height - 8) - 4;
    return `${x},${y}`;
  });

  const smoothPoints = points.map((point, i) => {
    if (i === 0) return `M ${point}`;
    const [prevX, prevY] = points[i - 1].split(',').map(Number);
    const [currX, currY] = point.split(',').map(Number);
    const cpx1 = prevX + (currX - prevX) * 0.4;
    const cpx2 = currX - (currX - prevX) * 0.4;
    return `C ${cpx1},${prevY} ${cpx2},${currY} ${currX},${currY}`;
  }).join(' ');

  return (
    <path
      d={smoothPoints}
      fill="none"
      stroke={color}
      strokeWidth="2"
      strokeLinecap="round"
    />
  );
}

export function TaskThroughputChart({ className }: TaskThroughputChartProps) {
  const { t } = useTranslation();
  const data = generateSeriesData();
  const chartWidth = 500;
  const chartHeight = 160;

  return (
    <div className={cn('rounded-2xl border border-gray-200/60 bg-white p-6', className)}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <BarChart3 className="size-4 text-gray-400" />
          <h3 className="text-sm font-bold text-[hsl(0,0%,8%)]">{t('taskBoard.taskThroughput')}</h3>
        </div>
        <button className="inline-flex items-center gap-1 rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-xs font-medium text-gray-600">
          {t('taskBoard.thisWeek')}
          <svg className="size-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polyline points="6 9 12 15 18 9" />
          </svg>
        </button>
      </div>

      <div className="mt-4 flex gap-6">
        <div className="flex-1">
          <svg width="100%" height={chartHeight} viewBox={`0 0 ${chartWidth} ${chartHeight}`} preserveAspectRatio="none">
            {[0, 10, 20, 30].map(v => (
              <g key={v}>
                <line
                  x1="0"
                  y1={chartHeight - (v / 30) * (chartHeight - 16) - 8}
                  x2={chartWidth}
                  y2={chartHeight - (v / 30) * (chartHeight - 16) - 8}
                  stroke="#f0f0f0"
                  strokeWidth="1"
                />
                <text
                  x="-4"
                  y={chartHeight - (v / 30) * (chartHeight - 16) - 4}
                  textAnchor="end"
                  className="fill-gray-400"
                  fontSize="10"
                >
                  {v}
                </text>
              </g>
            ))}
            {SERIES.map(s => (
              <LinePath
                key={s.key}
                data={data[s.key]}
                color={s.color}
                width={chartWidth}
                height={chartHeight}
              />
            ))}
          </svg>
          <div className="mt-1 flex justify-between px-0">
            {DAYS.map(day => (
              <span key={day} className="text-[10px] text-gray-400">{day}</span>
            ))}
          </div>
        </div>

        <div className="flex flex-col gap-2 border-l border-gray-100 pl-6">
          {SERIES.map(s => (
            <div key={s.key} className="flex items-center gap-2 text-xs">
              <span className="size-2.5 rounded-full" style={{ backgroundColor: s.color }} />
              <span className="text-gray-600">{t(s.labelKey as never)}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
