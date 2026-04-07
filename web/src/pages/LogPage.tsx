import { useState, useMemo } from 'react';
import { Link } from 'react-router-dom';
import {
  Loader2, Clock, GitMerge, XCircle, AlertCircle,
  GitBranch, ChevronRight, Bot, ExternalLink,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { mockProjects, getProjectTasks, getAgentTasks } from '@/data/mockWorkflows';
import type { Agent, AgentTask, AgentType, Project, TaskStatus } from '@/types/agent';

// ─── Types ─────────────────────────────────────────────────────────────────────

type FilterTab = 'all' | 'running' | 'waiting' | 'merged' | 'closed' | 'fail';

// ─── Warm palette ─────────────────────────────────────────────────────────────
//
//  PAGE_BG     #F2EDE4   warm sand — outermost background
//  SIDEBAR_BG  #EAE4DA   warm linen — sidebar
//  SURFACE     #FDFAF6   warm cream — cards, headers, panels
//  BORDER      #DDD7CE   warm taupe — all borders
//  DIVIDER     #EAE4DA   soft row dividers (same as sidebar)
//  ACCENT      #B5622A   muted terracotta — brand colour
//  ACCENT_DIM  #F2E4D8   light terracotta tint — hover / active bg
//  HOVER_ROW   #F5EDE5   row hover
//  TEXT_LINK   #8B4218   dark terracotta — active/hover text

const C = {
  pageBg:    'bg-[#F2EDE4]',
  sidebarBg: 'bg-[#EAE4DA]',
  surface:   'bg-[#FDFAF6]',
  border:    'border-[#DDD7CE]',
  divider:   'border-[#EAE4DA]',
  accent:    '#B5622A',
  accentDim: '#F2E4D8',
  hoverRow:  'hover:bg-[#F5EDE5]',
} as const;

// ─── Status meta ───────────────────────────────────────────────────────────────

const STATUS_META: Record<TaskStatus, {
  label: string; filterKey: FilterTab;
  icon: React.ElementType; dot: string; iconCls: string; badge: string;
}> = {
  running: { label: 'Doing',   filterKey: 'running', icon: Loader2,
    dot: 'bg-amber-400',   iconCls: 'text-amber-500 animate-spin',
    badge: 'text-amber-700 bg-amber-50 border-amber-200' },
  waiting: { label: 'Pending', filterKey: 'waiting', icon: Clock,
    dot: 'bg-yellow-400',  iconCls: 'text-yellow-600',
    badge: 'text-yellow-700 bg-yellow-50 border-yellow-200' },
  merged:  { label: 'Merged',  filterKey: 'merged',  icon: GitMerge,
    dot: 'bg-emerald-500', iconCls: 'text-emerald-600',
    badge: 'text-emerald-700 bg-emerald-50 border-emerald-200' },
  closed:  { label: 'Closed',  filterKey: 'closed',  icon: XCircle,
    dot: 'bg-stone-300',   iconCls: 'text-stone-400',
    badge: 'text-stone-500 bg-stone-100 border-stone-200' },
  failed:  { label: 'Failed',  filterKey: 'fail',    icon: AlertCircle,
    dot: 'bg-red-400',     iconCls: 'text-red-500',
    badge: 'text-red-700 bg-red-50 border-red-200' },
  error:   { label: 'Error',   filterKey: 'fail',    icon: AlertCircle,
    dot: 'bg-red-400',     iconCls: 'text-red-500',
    badge: 'text-red-700 bg-red-50 border-red-200' },
};

// Softer, warmer agent type colours
const AGENT_COLORS: Record<AgentType, { dot: string; badge: string; ring: string }> = {
  Sophie: {
    dot:  'bg-[#C07040]',
    badge:'text-[#7A3A10] bg-[#F8EDDF] border-[#E0BFA0]',
    ring: 'ring-[#E0BFA0]',
  },
  Tela: {
    dot:  'bg-teal-400',
    badge:'text-teal-800 bg-teal-50 border-teal-200',
    ring: 'ring-teal-200',
  },
};

// ─── Helpers ───────────────────────────────────────────────────────────────────

function timeAgo(iso?: string): string {
  if (!iso) return '—';
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 60)    return `${Math.round(s)}s ago`;
  if (s < 3600)  return `${Math.round(s / 60)}m ago`;
  if (s < 86400) return `${Math.round(s / 3600)}h ago`;
  return `${Math.round(s / 86400)}d ago`;
}

function fmtDuration(s?: number): string {
  if (!s) return '';
  const m = Math.floor(s / 60);
  return s < 60 ? `${s}s` : s % 60 ? `${m}m ${s % 60}s` : `${m}m`;
}

function countTasks(tasks: AgentTask[]) {
  return {
    running: tasks.filter(t => t.status === 'running').length,
    waiting: tasks.filter(t => t.status === 'waiting').length,
    merged:  tasks.filter(t => t.status === 'merged').length,
    closed:  tasks.filter(t => t.status === 'closed').length,
    fail:    tasks.filter(t => t.status === 'failed' || t.status === 'error').length,
  };
}

function projectRunningCount(p: Project) {
  return p.agents.filter(a => a.status === 'busy').length;
}

// ─── Status icon / badge ───────────────────────────────────────────────────────

function StatusIcon({ status }: { status: TaskStatus }) {
  const { icon: Icon, iconCls } = STATUS_META[status];
  return <Icon className={cn('size-4 shrink-0', iconCls)} />;
}

function StatusBadge({ status }: { status: TaskStatus }) {
  const { dot, badge, label } = STATUS_META[status];
  return (
    <span className={cn(
      'inline-flex items-center gap-1 px-2 py-0.5 rounded-full border text-xs font-medium shrink-0',
      badge,
    )}>
      <span className={cn('size-1.5 rounded-full', dot)} />
      {label}
    </span>
  );
}

// ─── Task row ──────────────────────────────────────────────────────────────────

function TaskRow({ task }: { task: AgentTask }) {
  const timeRef = (task.status === 'running' || task.status === 'waiting')
    ? task.startTime : task.endTime;
  const ac = AGENT_COLORS[task.agentType];

  return (
    <Link
      to={`/task/${task.id}`}
      className={cn(
        'group flex items-start gap-3 px-5 py-3.5 transition-colors',
        `border-b ${C.divider} last:border-b-0`,
        C.hoverRow,
      )}
    >
      <span className="mt-0.5 shrink-0">
        <StatusIcon status={task.status} />
      </span>

      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className={cn(
            'inline-flex items-center gap-1 px-1.5 py-0 rounded border text-[11px] font-medium shrink-0',
            ac.badge,
          )}>
            <span className={cn('size-1 rounded-full', ac.dot)} />
            {task.agentName}
          </span>
          <span className="text-sm font-medium text-stone-700 group-hover:text-[#8B4218] transition-colors truncate">
            {task.title}
          </span>
        </div>

        <div className="flex items-center gap-3 mt-0.5 flex-wrap text-xs text-stone-400">
          {task.metadata?.branch && (
            <span className="flex items-center gap-1">
              <GitBranch className="size-3 shrink-0" />
              <span className="font-mono">{task.metadata.branch}</span>
            </span>
          )}
          {task.metadata?.commit && (
            <code className="bg-transparent p-0 text-[11px] text-stone-300">
              {task.metadata.commit.slice(0, 7)}
            </code>
          )}
          {task.duration && <span>{fmtDuration(task.duration)}</span>}
          {task.error && <span className="text-red-400 truncate max-w-xs">{task.error}</span>}
        </div>
      </div>

      <div className="flex items-center gap-3 shrink-0 ml-2">
        <span className="text-xs text-stone-400 hidden sm:block whitespace-nowrap">
          {timeAgo(timeRef)}
        </span>
        <StatusBadge status={task.status} />
        <ChevronRight className="size-3.5 text-stone-300 opacity-0 group-hover:opacity-100 transition-opacity" />
      </div>
    </Link>
  );
}

// ─── Filter bar ────────────────────────────────────────────────────────────────

function FilterBar({
  filter, counts, total, onChange,
}: {
  filter: FilterTab;
  counts: ReturnType<typeof countTasks>;
  total: number;
  onChange: (f: FilterTab) => void;
}) {
  const tabs: Array<{ key: FilterTab; label: string; count: number }> = [
    { key: 'all',     label: 'All',     count: total           },
    { key: 'running', label: 'Doing',   count: counts.running  },
    { key: 'waiting', label: 'Pending', count: counts.waiting  },
    { key: 'merged',  label: 'Merged',  count: counts.merged   },
    { key: 'closed',  label: 'Closed',  count: counts.closed   },
    { key: 'fail',    label: 'Fail',    count: counts.fail     },
  ];
  return (
    <div className={cn('flex items-center border-b px-4', C.surface, C.border)}>
      {tabs.map(({ key, label, count }) => {
        const active = filter === key;
        return (
          <button
            key={key}
            onClick={() => onChange(key)}
            className={cn(
              'flex items-center gap-1.5 px-3 py-2.5 text-sm border-b-2 -mb-px transition-colors',
              active
                ? 'font-medium border-[#B5622A] text-[#8B4218]'
                : 'border-transparent text-stone-400 hover:text-stone-600 hover:border-[#C4B5A8]',
            )}
          >
            {label}
            {count > 0 && (
              <span className={cn(
                'px-1.5 py-0 rounded text-xs font-mono leading-5',
                active
                  ? 'bg-[#F2E4D8] text-[#8B4218]'
                  : 'bg-[#E8E2D8] text-stone-400',
              )}>
                {count}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}

// ─── Sidebar project item ──────────────────────────────────────────────────────

function SidebarProject({
  project, selected, onClick,
}: {
  project: Project; selected: boolean; onClick: () => void;
}) {
  const running = projectRunningCount(project);
  return (
    <button
      onClick={onClick}
      className={cn(
        'w-full flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-[13px] transition-colors',
        selected
          ? `${C.surface} text-stone-800 font-medium shadow-sm ring-1 ring-[#DDD7CE]`
          : 'text-stone-500 hover:text-stone-700 hover:bg-[#E2DDD3]',
      )}
    >
      <span className="relative size-2 shrink-0">
        <span className={cn(
          'block size-2 rounded-full',
          running > 0 ? 'bg-amber-400' : 'bg-[#C4B5A8]',
        )} />
        {running > 0 && (
          <span className="absolute inset-0 rounded-full bg-amber-300 animate-ping opacity-60" />
        )}
      </span>
      <span className="flex-1 truncate text-left">{project.name}</span>
      <span className="text-[11px] font-mono text-stone-400 shrink-0">
        {project.agents.length}
      </span>
    </button>
  );
}

// ─── Agent chip ────────────────────────────────────────────────────────────────

function AgentChip({
  agent, selected, onClick,
}: {
  agent: Agent; selected: boolean; onClick: () => void;
}) {
  const ac = AGENT_COLORS[agent.agentType];
  const busy = agent.status === 'busy';
  return (
    <button
      onClick={onClick}
      className={cn(
        'inline-flex items-center gap-1 px-2 py-0.5 rounded-full border text-[11px] font-medium transition-all',
        selected
          ? cn(ac.badge, 'shadow-sm ring-1', ac.ring)
          : busy
            ? 'text-amber-700 bg-amber-50 border-amber-200 hover:bg-amber-100'
            : 'text-stone-500 bg-[#F2EDE4] border-[#DDD7CE] hover:bg-[#E8E2D8]',
      )}
    >
      <span className={cn('size-1.5 rounded-full', ac.dot)} />
      {agent.name}
      {busy && <span className="size-1.5 rounded-full bg-amber-400 animate-pulse ml-0.5" />}
    </button>
  );
}

// ─── Main page ─────────────────────────────────────────────────────────────────

export default function LogPage() {
  const [selectedProjectId, setSelectedProjectId] = useState<string>(mockProjects[0].id);
  const [selectedAgentId,   setSelectedAgentId]   = useState<string | null>(null);
  const [filter,            setFilter]            = useState<FilterTab>('all');

  const project = useMemo(
    () => mockProjects.find(p => p.id === selectedProjectId) ?? mockProjects[0],
    [selectedProjectId],
  );

  const baseTasks = useMemo(() => {
    if (selectedAgentId) {
      const agent = project.agents.find(a => a.id === selectedAgentId);
      return agent ? getAgentTasks(agent) : [];
    }
    return getProjectTasks(project);
  }, [project, selectedAgentId]);

  const counts = useMemo(() => countTasks(baseTasks), [baseTasks]);

  const filtered = useMemo(() => {
    if (filter === 'all')  return baseTasks;
    if (filter === 'fail') return baseTasks.filter(t => t.status === 'failed' || t.status === 'error');
    return baseTasks.filter(t => t.status === filter);
  }, [baseTasks, filter]);

  return (
    <div className={cn('flex flex-col h-screen overflow-hidden', C.pageBg)}>

      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <header className={cn(
        'h-12 shrink-0 flex items-center px-5 gap-3 border-b',
        C.surface, C.border,
      )}>
        <div
          className="size-6 rounded-md flex items-center justify-center shrink-0"
          style={{ background: C.accent }}
        >
          <Bot className="size-3.5 text-white" />
        </div>
        <span className="text-sm font-semibold text-stone-700 tracking-tight">Nexus</span>
      </header>

      <div className="flex flex-1 overflow-hidden">

        {/* ── Sidebar ──────────────────────────────────────────────────────── */}
        <aside className={cn('w-52 shrink-0 border-r overflow-y-auto', C.sidebarBg, C.border)}>
          <nav className="p-2 pt-3">
            <p className="text-[10px] font-semibold text-stone-400 uppercase tracking-widest px-2.5 mb-2">
              Projects
            </p>
            <div className="space-y-0.5">
              {mockProjects.map(p => (
                <SidebarProject
                  key={p.id}
                  project={p}
                  selected={selectedProjectId === p.id}
                  onClick={() => {
                    setSelectedProjectId(p.id);
                    setSelectedAgentId(null);
                    setFilter('all');
                  }}
                />
              ))}
            </div>
          </nav>
        </aside>

        {/* ── Main ─────────────────────────────────────────────────────────── */}
        <main className={cn('flex-1 overflow-y-auto min-w-0', C.pageBg)}>

          {/* Project header */}
          <div className={cn('border-b px-6 py-4', C.surface, C.border)}>
            <div className="flex items-start justify-between gap-4 flex-wrap">
              <div>
                <div className="flex items-center gap-2">
                  <h1 className="text-base font-semibold text-stone-800">{project.name}</h1>
                  <a
                    href={`https://github.com/${project.repo}`}
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-center gap-1 text-xs text-stone-400 hover:text-[#8B4218] transition-colors"
                    onClick={e => e.stopPropagation()}
                  >
                    <ExternalLink className="size-3" />
                    {project.repo}
                  </a>
                </div>
                <p className="text-sm text-stone-400 mt-0.5">{project.description}</p>
              </div>

              <div className="flex items-center gap-3 text-xs text-stone-400 flex-wrap">
                {counts.running > 0 && (
                  <span className="flex items-center gap-1 text-amber-600">
                    <span className="size-1.5 rounded-full bg-amber-400 animate-pulse" />
                    {counts.running} doing
                  </span>
                )}
                {counts.waiting > 0 && <span>{counts.waiting} pending</span>}
                {counts.merged  > 0 && <span className="text-emerald-600">{counts.merged} merged</span>}
                {counts.closed  > 0 && <span>{counts.closed} closed</span>}
                {counts.fail    > 0 && <span className="text-red-400">{counts.fail} failed</span>}
              </div>
            </div>

            {/* Agent chips */}
            <div className="flex items-center gap-1.5 mt-3 flex-wrap">
              <button
                onClick={() => { setSelectedAgentId(null); setFilter('all'); }}
                className={cn(
                  'inline-flex items-center px-2 py-0.5 rounded-full border text-[11px] font-medium transition-colors',
                  selectedAgentId === null
                    ? 'text-stone-700 bg-[#DDD7CE] border-[#C4B5A8]'
                    : 'text-stone-400 bg-[#F2EDE4] border-[#DDD7CE] hover:bg-[#E8E2D8]',
                )}
              >
                All
              </button>
              {project.agents.map(a => (
                <AgentChip
                  key={a.id}
                  agent={a}
                  selected={selectedAgentId === a.id}
                  onClick={() => { setSelectedAgentId(a.id); setFilter('all'); }}
                />
              ))}
            </div>
          </div>

          {/* Filter tab bar */}
          <FilterBar
            filter={filter}
            counts={counts}
            total={baseTasks.length}
            onChange={f => setFilter(f)}
          />

          {/* Task list */}
          <div className={cn(
            'm-4 rounded-xl border shadow-sm overflow-hidden',
            C.surface, C.border,
          )}>
            {filtered.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-20 gap-3">
                <Bot className="size-8 text-[#C4B5A8]" />
                <p className="text-sm text-stone-400">No tasks</p>
              </div>
            ) : (
              filtered.map(task => <TaskRow key={task.id} task={task} />)
            )}
          </div>

        </main>
      </div>
    </div>
  );
}
