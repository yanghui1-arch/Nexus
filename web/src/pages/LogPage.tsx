import { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  CheckCircle2,
  XCircle,
  AlertCircle,
  Clock,
  Loader2,
  GitMerge,
  GitPullRequest,
  ChevronRight,
  ChevronDown,
  Activity,
  Timer,
  Search,
  RefreshCw,
  Zap,
  Circle,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { mockAgents } from '@/data/mockWorkflows';
import type { Agent, AgentTask, TaskStatus } from '@/types/agent';

// ─── Types ───────────────────────────────────────────────────────────────────

type ExtendedTaskStatus = TaskStatus | 'merged' | 'open' | 'pending' | 'closed';

// ─── Status configuration — light-system-friendly colors ─────────────────────

const statusConfig: Record<
  ExtendedTaskStatus,
  {
    icon: React.ReactNode;
    dotColor: string;      // solid dot / badge fill
    textColor: string;     // label text
    bgColor: string;       // pill / section header bg
    borderColor: string;   // section border accent
    label: string;
  }
> = {
  running: {
    icon: <Loader2 className="h-3.5 w-3.5 animate-spin" />,
    dotColor: 'bg-amber-400',
    textColor: 'text-amber-700',
    bgColor: 'bg-amber-50',
    borderColor: 'border-amber-200',
    label: 'Running',
  },
  waiting: {
    icon: <Clock className="h-3.5 w-3.5" />,
    dotColor: 'bg-slate-400',
    textColor: 'text-slate-600',
    bgColor: 'bg-slate-50',
    borderColor: 'border-slate-200',
    label: 'Waiting',
  },
  completed: {
    icon: <CheckCircle2 className="h-3.5 w-3.5" />,
    dotColor: 'bg-emerald-500',
    textColor: 'text-emerald-700',
    bgColor: 'bg-emerald-50',
    borderColor: 'border-emerald-200',
    label: 'Passed',
  },
  failed: {
    icon: <XCircle className="h-3.5 w-3.5" />,
    dotColor: 'bg-red-500',
    textColor: 'text-red-700',
    bgColor: 'bg-red-50',
    borderColor: 'border-red-200',
    label: 'Failed',
  },
  error: {
    icon: <AlertCircle className="h-3.5 w-3.5" />,
    dotColor: 'bg-orange-500',
    textColor: 'text-orange-700',
    bgColor: 'bg-orange-50',
    borderColor: 'border-orange-200',
    label: 'Error',
  },
  merged: {
    icon: <GitMerge className="h-3.5 w-3.5" />,
    dotColor: 'bg-violet-500',
    textColor: 'text-violet-700',
    bgColor: 'bg-violet-50',
    borderColor: 'border-violet-200',
    label: 'Merged',
  },
  open: {
    icon: <GitPullRequest className="h-3.5 w-3.5" />,
    dotColor: 'bg-blue-500',
    textColor: 'text-blue-700',
    bgColor: 'bg-blue-50',
    borderColor: 'border-blue-200',
    label: 'Open',
  },
  pending: {
    icon: <Clock className="h-3.5 w-3.5" />,
    dotColor: 'bg-amber-400',
    textColor: 'text-amber-700',
    bgColor: 'bg-amber-50',
    borderColor: 'border-amber-200',
    label: 'Pending',
  },
  closed: {
    icon: <CheckCircle2 className="h-3.5 w-3.5" />,
    dotColor: 'bg-slate-400',
    textColor: 'text-slate-500',
    bgColor: 'bg-slate-50',
    borderColor: 'border-slate-200',
    label: 'Closed',
  },
};

const agentStatusConfig = {
  online: { dot: 'bg-emerald-400', label: 'Online', text: 'text-emerald-700' },
  busy:   { dot: 'bg-amber-400',   label: 'Busy',   text: 'text-amber-700'  },
  offline:{ dot: 'bg-slate-300',   label: 'Offline', text: 'text-slate-400' },
};

// ─── Helpers ──────────────────────────────────────────────────────────────────

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  const remaining = seconds % 60;
  if (minutes < 60) return remaining > 0 ? `${minutes}m ${remaining}s` : `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;
  return remainingMinutes > 0 ? `${hours}h ${remainingMinutes}m` : `${hours}h`;
}

function formatRelativeTime(isoString: string): string {
  const date = new Date(isoString);
  const now = new Date();
  const diff = now.getTime() - date.getTime();
  const minutes = Math.floor(diff / 60000);
  const hours = Math.floor(minutes / 60);
  const days = Math.floor(hours / 24);
  if (minutes < 1) return 'just now';
  if (minutes < 60) return `${minutes}m ago`;
  if (hours < 24) return `${hours}h ago`;
  if (days < 7) return `${days}d ago`;
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

function getTaskCategory(task: AgentTask): ExtendedTaskStatus {
  if (task.status === 'running') return 'running';
  if (task.status === 'waiting') return 'pending';
  if (task.status === 'failed') return 'failed';
  if (task.status === 'error') return 'error';
  if (task.status === 'completed') {
    return task.metadata?.branch === 'main' ? 'merged' : 'closed';
  }
  return task.status;
}

// ─── StatusDot ────────────────────────────────────────────────────────────────

function StatusDot({ status }: { status: ExtendedTaskStatus }) {
  const cfg = statusConfig[status];
  const isRunning = status === 'running';
  return (
    <span className="relative flex h-4 w-4 items-center justify-center flex-shrink-0">
      {isRunning && (
        <span className={cn('absolute inset-0 animate-ping rounded-full opacity-40', cfg.dotColor)} />
      )}
      <span className={cn('rounded-full', isRunning ? 'h-2.5 w-2.5' : 'h-2.5 w-2.5', cfg.dotColor)} />
    </span>
  );
}

// ─── StatusBadge ─────────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: ExtendedTaskStatus }) {
  const cfg = statusConfig[status];
  return (
    <span className={cn(
      'inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium',
      cfg.bgColor, cfg.textColor
    )}>
      {cfg.icon}
      {cfg.label}
    </span>
  );
}

// ─── TaskRow ─────────────────────────────────────────────────────────────────

interface TaskRowProps {
  task: AgentTask;
  onClick: () => void;
  isLast?: boolean;
}

function TaskRow({ task, onClick, isLast }: TaskRowProps) {
  const category = getTaskCategory(task);
  const isRunning = task.status === 'running';

  return (
    <button
      onClick={onClick}
      className={cn(
        'w-full group flex items-center gap-3 px-5 py-2.5',
        'cursor-pointer',
        'hover:bg-slate-50 active:bg-slate-100 transition-colors duration-100',
        !isLast && 'border-b border-slate-100'
      )}
    >
      {/* Status dot */}
      <StatusDot status={category} />

      {/* Task info */}
      <div className="flex-1 min-w-0 text-left">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-sm font-medium text-slate-800 group-hover:text-slate-900 truncate">
            {task.title}
          </span>
          {task.metadata?.branch && (
            <span className="flex-shrink-0 text-xs px-1.5 py-0.5 rounded bg-slate-100 text-slate-500 font-mono">
              {task.metadata.branch}
            </span>
          )}
          {task.metadata?.commit && (
            <span className="flex-shrink-0 text-xs font-mono text-slate-400">
              {task.metadata.commit.slice(0, 7)}
            </span>
          )}
        </div>
        <div className="text-xs text-slate-400 mt-0.5">{task.id}</div>
      </div>

      {/* Duration / time */}
      <div className="flex-shrink-0 text-right space-y-0.5">
        {isRunning && task.startTime ? (
          <div className="flex items-center gap-1 text-xs text-amber-600 justify-end">
            <Timer className="h-3 w-3" />
            {formatDuration(Math.floor((Date.now() - new Date(task.startTime).getTime()) / 1000))}
          </div>
        ) : task.duration ? (
          <div className="text-xs text-slate-500">{formatDuration(task.duration)}</div>
        ) : null}
        {task.endTime && (
          <div className="text-xs text-slate-400">{formatRelativeTime(task.endTime)}</div>
        )}
      </div>

      {/* Arrow */}
      <ChevronRight className="h-4 w-4 text-slate-300 group-hover:text-slate-500 transition-colors flex-shrink-0" />
    </button>
  );
}

// ─── Section within expanded agent ───────────────────────────────────────────

interface TaskSectionProps {
  status: ExtendedTaskStatus;
  tasks: AgentTask[];
  onTaskClick: (id: string) => void;
}

function TaskSection({ status, tasks, onTaskClick }: TaskSectionProps) {
  const cfg = statusConfig[status];
  if (tasks.length === 0) return null;
  return (
    <div>
      {/* Section header */}
      <div className={cn(
        'flex items-center gap-2 px-5 py-2 border-b',
        cfg.bgColor,
        cfg.borderColor,
      )}>
        <span className={cn('flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider', cfg.textColor)}>
          {cfg.icon}
          {cfg.label}
        </span>
        <span className={cn('text-xs', cfg.textColor, 'opacity-60')}>{tasks.length}</span>
      </div>
      {/* Task rows */}
      {tasks.map((task, i) => (
        <TaskRow
          key={task.id}
          task={task}
          onClick={() => onTaskClick(task.id)}
          isLast={i === tasks.length - 1}
        />
      ))}
    </div>
  );
}

// ─── AgentCard ───────────────────────────────────────────────────────────────

interface AgentCardProps {
  agent: Agent;
  onTaskClick: (taskId: string) => void;
  isExpanded: boolean;
  onToggle: () => void;
}

function AgentCard({ agent, onTaskClick, isExpanded, onToggle }: AgentCardProps) {
  const agStatus = agentStatusConfig[agent.status];

  // Collect ALL tasks across every bucket
  const allTasks = useMemo(() => {
    const tasks: AgentTask[] = [];
    if (agent.currentTask) tasks.push(agent.currentTask);
    tasks.push(...agent.taskQueue);
    tasks.push(...agent.completedTasks);
    return tasks;
  }, [agent]);

  // Group by category — preserving ALL statuses
  const groups = useMemo(() => {
    const map: Partial<Record<ExtendedTaskStatus, AgentTask[]>> = {};
    for (const task of allTasks) {
      const cat = getTaskCategory(task);
      if (!map[cat]) map[cat] = [];
      map[cat]!.push(task);
    }
    return map;
  }, [allTasks]);

  // Summary counts for the collapsed header badges
  const counts = useMemo(() => {
    const result: Partial<Record<ExtendedTaskStatus, number>> = {};
    for (const [k, v] of Object.entries(groups)) {
      result[k as ExtendedTaskStatus] = v.length;
    }
    return result;
  }, [groups]);

  const totalTasks = allTasks.length;

  // Section render order
  const sectionOrder: ExtendedTaskStatus[] = [
    'running', 'pending', 'open', 'failed', 'error', 'merged', 'closed', 'waiting', 'completed',
  ];

  return (
    <div className={cn(
      'rounded-lg border bg-white transition-all duration-200',
      isExpanded ? 'border-slate-300 shadow-sm' : 'border-slate-200 hover:border-slate-300',
    )}>
      {/* ── Agent header (toggle) ── */}
      <button
        onClick={onToggle}
        className="w-full flex items-center gap-3 px-4 py-3 hover:bg-slate-50 transition-colors rounded-lg cursor-pointer"
        aria-expanded={isExpanded}
      >
        {/* Expand chevron */}
        <ChevronDown className={cn(
          'h-4 w-4 text-slate-400 transition-transform duration-200 flex-shrink-0',
          isExpanded && 'rotate-180'
        )} />

        {/* Agent status indicator */}
        <span className="relative flex-shrink-0">
          <span className={cn('w-2.5 h-2.5 rounded-full inline-block', agStatus.dot)} />
          {agent.status === 'busy' && (
            <span className="absolute inset-0 w-2.5 h-2.5 rounded-full bg-amber-400 animate-ping opacity-50" />
          )}
        </span>

        {/* Agent name + status label */}
        <div className="flex-1 text-left min-w-0">
          <span className="text-sm font-semibold text-slate-800">{agent.name}</span>
          <span className={cn('text-xs ml-2', agStatus.text)}>{agStatus.label}</span>
        </div>

        {/* Summary badges */}
        <div className="flex items-center gap-1.5 flex-wrap">
          {(counts.running ?? 0) > 0 && (
            <StatusBadge status="running" />
          )}
          {(counts.pending ?? 0) > 0 && (
            <span className="text-xs px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 font-medium">
              {counts.pending} pending
            </span>
          )}
          {(counts.merged ?? 0) > 0 && (
            <span className="text-xs px-2 py-0.5 rounded-full bg-violet-50 text-violet-700 font-medium">
              {counts.merged} merged
            </span>
          )}
          {(counts.closed ?? 0) > 0 && (
            <span className="text-xs px-2 py-0.5 rounded-full bg-slate-100 text-slate-500 font-medium">
              {counts.closed} closed
            </span>
          )}
          {(counts.failed ?? 0) + (counts.error ?? 0) > 0 && (
            <span className="text-xs px-2 py-0.5 rounded-full bg-red-50 text-red-700 font-medium">
              {(counts.failed ?? 0) + (counts.error ?? 0)} failed
            </span>
          )}
          {totalTasks === 0 && (
            <span className="text-xs text-slate-400">No tasks</span>
          )}
        </div>
      </button>

      {/* ── Expanded content ── */}
      {isExpanded && (
        <div className="border-t border-slate-100 divide-y divide-slate-100">
          {totalTasks === 0 ? (
            <div className="px-5 py-10 text-center">
              <div className="w-10 h-10 rounded-full bg-slate-50 flex items-center justify-center mx-auto mb-3">
                <Activity className="h-5 w-5 text-slate-300" />
              </div>
              <p className="text-sm text-slate-400">No tasks assigned to this agent</p>
            </div>
          ) : (
            sectionOrder.map(status => (
              <TaskSection
                key={status}
                status={status}
                tasks={groups[status] ?? []}
                onTaskClick={onTaskClick}
              />
            ))
          )}
        </div>
      )}
    </div>
  );
}

// ─── Summary stat pill ───────────────────────────────────────────────────────

interface StatPillProps {
  label: string;
  value: number;
  color: string;
  icon: React.ReactNode;
}

function StatPill({ label, value, color, icon }: StatPillProps) {
  return (
    <div className={cn(
      'flex items-center gap-2 px-3 py-2 rounded-lg border text-sm',
      color
    )}>
      <span className="flex-shrink-0">{icon}</span>
      <span className="font-semibold tabular-nums">{value}</span>
      <span className="text-xs font-medium opacity-70">{label}</span>
    </div>
  );
}

// ─── LogPage ─────────────────────────────────────────────────────────────────

export default function LogPage() {
  const navigate = useNavigate();
  const [expandedAgents, setExpandedAgents] = useState<Set<string>>(new Set());
  const [searchQuery, setSearchQuery] = useState('');

  // ── Aggregate stats ──────────────────────────────────────────────────────
  const stats = useMemo(() => {
    const tally = { total: 0, running: 0, pending: 0, merged: 0, closed: 0, failed: 0 };
    for (const agent of mockAgents) {
      const tasks = [
        agent.currentTask,
        ...agent.taskQueue,
        ...agent.completedTasks,
      ].filter(Boolean) as AgentTask[];
      for (const t of tasks) {
        tally.total++;
        const cat = getTaskCategory(t);
        if (cat === 'running') tally.running++;
        else if (cat === 'pending') tally.pending++;
        else if (cat === 'merged') tally.merged++;
        else if (cat === 'closed') tally.closed++;
        else if (cat === 'failed' || cat === 'error') tally.failed++;
      }
    }
    return tally;
  }, []);

  const onlineAgents = mockAgents.filter(a => a.status !== 'offline').length;
  const busyAgents   = mockAgents.filter(a => a.status === 'busy').length;

  // ── Filtered agent list ──────────────────────────────────────────────────
  const filteredAgents = useMemo(() => {
    if (!searchQuery) return mockAgents;
    const q = searchQuery.toLowerCase();
    return mockAgents.filter(agent => {
      const allTasks = [
        agent.currentTask,
        ...agent.taskQueue,
        ...agent.completedTasks,
      ].filter(Boolean) as AgentTask[];
      return (
        agent.name.toLowerCase().includes(q) ||
        allTasks.some(t => t.title.toLowerCase().includes(q))
      );
    });
  }, [searchQuery]);

  const toggleAgent = (id: string) => {
    setExpandedAgents(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const expandAll = () => setExpandedAgents(new Set(filteredAgents.map(a => a.id)));
  const collapseAll = () => setExpandedAgents(new Set());

  return (
    <div className="min-h-screen bg-slate-50 text-slate-700">

      {/* ── Top Navigation ────────────────────────────────────────────────── */}
      <header className="sticky top-0 z-50 bg-white border-b border-slate-200 shadow-sm">
        <div className="max-w-5xl mx-auto px-4 sm:px-6">
          <div className="flex items-center justify-between h-12">

            {/* Brand */}
            <div className="flex items-center gap-2.5">
              <div className="flex items-center justify-center w-7 h-7 rounded-md bg-violet-600">
                <Zap className="h-4 w-4 text-white" />
              </div>
              <span className="text-sm font-semibold text-slate-900 tracking-tight">Nexus CI</span>
            </div>

            {/* Nav links */}
            <nav className="hidden md:flex items-center gap-1">
              {['Agents', 'Pipelines', 'Builds', 'Settings'].map(item => (
                <button
                  key={item}
                  className={cn(
                    'px-3 py-1.5 text-sm rounded-md transition-colors cursor-pointer',
                    item === 'Agents'
                      ? 'bg-slate-100 text-slate-900 font-medium'
                      : 'text-slate-500 hover:text-slate-800 hover:bg-slate-50'
                  )}
                >
                  {item}
                </button>
              ))}
            </nav>

            {/* Right side */}
            <div className="flex items-center gap-3">
              <button
                className="p-1.5 text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded-md transition-colors cursor-pointer"
                title="Refresh"
              >
                <RefreshCw className="h-4 w-4" />
              </button>
              <div className="h-4 w-px bg-slate-200" />
              <div className="flex items-center gap-1.5">
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-60"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                </span>
                <span className="text-xs text-slate-500">
                  <span className="font-medium text-slate-700">{onlineAgents}</span> agents
                </span>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* ── Pipeline identity bar (Buildkite-style) ────────────────────────── */}
      <div className="bg-white border-b border-slate-200">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 py-4">
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="flex items-center gap-2 text-xs text-slate-400 mb-1">
                <span className="cursor-pointer hover:text-violet-600 transition-colors">yanghui1-arch</span>
                <span>/</span>
                <span className="cursor-pointer hover:text-violet-600 transition-colors font-medium text-slate-600">Nexus</span>
              </div>
              <h1 className="text-xl font-semibold text-slate-900">Agents</h1>
              <p className="text-sm text-slate-500 mt-0.5">CI task queue across all running agents</p>
            </div>

            {/* Summary stat pills */}
            <div className="hidden sm:flex flex-wrap gap-2 items-center">
              <StatPill
                label="Running"
                value={stats.running}
                color="bg-amber-50 border-amber-200 text-amber-700"
                icon={<Loader2 className="h-3.5 w-3.5 animate-spin" />}
              />
              <StatPill
                label="Pending"
                value={stats.pending}
                color="bg-slate-100 border-slate-200 text-slate-600"
                icon={<Clock className="h-3.5 w-3.5" />}
              />
              <StatPill
                label="Merged"
                value={stats.merged}
                color="bg-violet-50 border-violet-200 text-violet-700"
                icon={<GitMerge className="h-3.5 w-3.5" />}
              />
              <StatPill
                label="Failed"
                value={stats.failed}
                color="bg-red-50 border-red-200 text-red-700"
                icon={<XCircle className="h-3.5 w-3.5" />}
              />
            </div>
          </div>
        </div>
      </div>

      {/* ── Main content ──────────────────────────────────────────────────── */}
      <main className="max-w-5xl mx-auto px-4 sm:px-6 py-5">

        {/* Toolbar */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">

          {/* Search */}
          <div className="relative w-full sm:w-72">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-400 pointer-events-none" />
            <input
              type="text"
              placeholder="Search agents or tasks…"
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              className={cn(
                'w-full pl-8 pr-3 py-2 text-sm rounded-lg border',
                'border-slate-200 bg-white text-slate-800 placeholder-slate-400',
                'focus:outline-none focus:ring-2 focus:ring-violet-400/40 focus:border-violet-400',
                'transition-all'
              )}
            />
          </div>

          {/* Expand / collapse + count */}
          <div className="flex items-center gap-2 flex-shrink-0">
            <span className="text-xs text-slate-400">
              {filteredAgents.length} agent{filteredAgents.length !== 1 ? 's' : ''}
              {' · '}{stats.total} task{stats.total !== 1 ? 's' : ''}
            </span>
            <div className="h-4 w-px bg-slate-200" />
            <button
              onClick={expandAll}
              className="text-xs text-slate-500 hover:text-slate-800 cursor-pointer transition-colors px-2 py-1 rounded hover:bg-slate-100"
            >
              Expand all
            </button>
            <button
              onClick={collapseAll}
              className="text-xs text-slate-500 hover:text-slate-800 cursor-pointer transition-colors px-2 py-1 rounded hover:bg-slate-100"
            >
              Collapse all
            </button>
            <div className="flex items-center gap-1 text-xs">
              <span className={cn(
                'px-2 py-0.5 rounded-full font-medium',
                busyAgents > 0 ? 'bg-amber-100 text-amber-700' : 'bg-slate-100 text-slate-500'
              )}>
                {busyAgents} busy
              </span>
            </div>
          </div>
        </div>

        {/* Agent list */}
        <div className="space-y-2">
          {filteredAgents.map(agent => (
            <AgentCard
              key={agent.id}
              agent={agent}
              onTaskClick={id => navigate(`/task/${id}`)}
              isExpanded={expandedAgents.has(agent.id)}
              onToggle={() => toggleAgent(agent.id)}
            />
          ))}
        </div>

        {/* Empty state */}
        {filteredAgents.length === 0 && (
          <div className="text-center py-20">
            <div className="w-14 h-14 rounded-full bg-slate-100 flex items-center justify-center mx-auto mb-4">
              <Search className="h-6 w-6 text-slate-300" />
            </div>
            <h3 className="text-sm font-semibold text-slate-600 mb-1">No agents found</h3>
            <p className="text-xs text-slate-400">Try adjusting your search</p>
          </div>
        )}
      </main>

      {/* ── Footer ────────────────────────────────────────────────────────── */}
      <footer className="border-t border-slate-200 bg-white mt-8">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 py-3 flex items-center justify-between text-xs text-slate-400">
          <div className="flex items-center gap-3">
            <span className="flex items-center gap-1.5">
              <Circle className="h-2 w-2 fill-emerald-400 text-emerald-400" />
              Nexus CI v0.1.0
            </span>
            <span>·</span>
            <span>{mockAgents.length} agents · {stats.total} tasks</span>
          </div>
          <span>Updated just now</span>
        </div>
      </footer>
    </div>
  );
}
