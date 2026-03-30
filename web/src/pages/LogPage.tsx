import { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  CheckCircle,
  XCircle,
  AlertCircle,
  Clock,
  Circle,
  Loader2,
  Terminal,
  GitBranch,
  Server,
  ChevronRight,
  Activity,
  Timer,
  Calendar,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { ScrollArea } from '@/components/ui/scroll-area';
import { mockAgents, getRunningTasks, getWaitingTasks, getCompletedTasks } from '@/data/mockWorkflows';
import type { AgentTask, TaskStatus } from '@/types/agent';

type TabType = 'running' | 'waiting' | 'completed';

const statusConfig: Record<TaskStatus, {
  icon: React.ReactNode;
  color: string;
  bgColor: string;
  borderColor: string;
  label: string;
  pulse?: boolean;
}> = {
  running: {
    icon: <Loader2 className="h-4 w-4 animate-spin" />,
    color: 'text-blue-500',
    bgColor: 'bg-blue-500',
    borderColor: 'border-blue-200',
    label: 'Running',
    pulse: true,
  },
  waiting: {
    icon: <Clock className="h-4 w-4" />,
    color: 'text-amber-500',
    bgColor: 'bg-amber-500',
    borderColor: 'border-amber-200',
    label: 'Waiting',
  },
  completed: {
    icon: <CheckCircle className="h-4 w-4" />,
    color: 'text-emerald-500',
    bgColor: 'bg-emerald-500',
    borderColor: 'border-emerald-200',
    label: 'Completed',
  },
  failed: {
    icon: <XCircle className="h-4 w-4" />,
    color: 'text-red-500',
    bgColor: 'bg-red-500',
    borderColor: 'border-red-200',
    label: 'Failed',
  },
  error: {
    icon: <AlertCircle className="h-4 w-4" />,
    color: 'text-orange-500',
    bgColor: 'bg-orange-500',
    borderColor: 'border-orange-200',
    label: 'Error',
  },
};

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  const remaining = seconds % 60;
  if (minutes < 60) {
    return remaining > 0 ? `${minutes}m ${remaining}s` : `${minutes}m`;
  }
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

  if (minutes < 1) return 'just now';
  if (minutes < 60) return `${minutes}m ago`;
  if (hours < 24) return `${hours}h ago`;
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

interface TaskListItemProps {
  task: AgentTask;
  isSelected: boolean;
  onClick: () => void;
}

function TaskListItem({ task, isSelected, onClick }: TaskListItemProps) {
  const config = statusConfig[task.status];

  return (
    <button
      onClick={onClick}
      className={cn(
        "w-full text-left p-4 border-b transition-all duration-200",
        "hover:bg-slate-50/50 dark:hover:bg-slate-800/50",
        "focus:outline-none focus:bg-slate-50 dark:focus:bg-slate-800/50",
        isSelected
          ? "bg-blue-50/80 dark:bg-blue-900/20 border-l-4 border-l-blue-500"
          : "border-l-4 border-l-transparent"
      )}
    >
      <div className="flex items-start gap-3">
        {/* Status Icon with pulse for running */}
        <div className="relative flex-shrink-0 mt-0.5">
          {task.status === 'running' ? (
            <div className="relative">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-blue-400 opacity-30"></span>
              <span className="relative inline-flex rounded-full p-1.5 bg-blue-100 dark:bg-blue-900/30">
                <Circle className="h-4 w-4 text-blue-500 fill-blue-500" />
              </span>
            </div>
          ) : (
            <span className={cn("inline-flex rounded-full p-1.5", config.color.replace('text-', 'bg-').replace('500', '100'), config.color.replace('text-', 'dark:bg-').replace('500', '900/30'))}>
              {config.icon}
            </span>
          )}
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          {/* Title */}
          <h3 className={cn(
            "font-medium text-sm leading-tight mb-1 pr-2",
            isSelected ? "text-blue-700 dark:text-blue-300" : "text-slate-900 dark:text-slate-100"
          )}>
            {task.title}
          </h3>

          {/* Agent & Meta */}
          <div className="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400 flex-wrap">
            <span className="flex items-center gap-1">
              <Server className="h-3 w-3" />
              {task.agentName}
            </span>
            {task.metadata?.branch && (
              <>
                <span className="text-slate-300 dark:text-slate-600">•</span>
                <span className="flex items-center gap-1">
                  <GitBranch className="h-3 w-3" />
                  {task.metadata.branch}
                </span>
              </>
            )}
          </div>

          {/* Timing */}
          <div className="flex items-center gap-3 mt-2 text-xs">
            {task.status === 'running' && task.startTime && (
              <span className="flex items-center gap-1 text-blue-600 dark:text-blue-400">
                <Timer className="h-3 w-3" />
                Running for {formatDuration(Math.floor((Date.now() - new Date(task.startTime).getTime()) / 1000))}
              </span>
            )}
            {task.status === 'waiting' && (
              <span className="flex items-center gap-1 text-amber-600 dark:text-amber-400">
                <Clock className="h-3 w-3" />
                Queued
              </span>
            )}
            {(task.status === 'completed' || task.status === 'failed' || task.status === 'error') && task.duration && (
              <span className="flex items-center gap-1 text-slate-500">
                <Activity className="h-3 w-3" />
                {formatDuration(task.duration)}
              </span>
            )}
            {task.endTime && (
              <span className="text-slate-400">
                {formatRelativeTime(task.endTime)}
              </span>
            )}
          </div>
        </div>

        {/* Arrow for selected */}
        {isSelected && (
          <ChevronRight className="h-4 w-4 text-blue-500 self-center flex-shrink-0" />
        )}
      </div>
    </button>
  );
}

interface TabButtonProps {
  active: boolean;
  onClick: () => void;
  label: string;
  count: number;
  color: 'blue' | 'amber' | 'emerald';
}

function TabButton({ active, onClick, label, count, color }: TabButtonProps) {
  const colorClasses = {
    blue: {
      active: 'bg-blue-500 text-white',
      inactive: 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800',
      badge: 'bg-blue-100 text-blue-700 dark:bg-blue-900/50 dark:text-blue-300',
    },
    amber: {
      active: 'bg-amber-500 text-white',
      inactive: 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800',
      badge: 'bg-amber-100 text-amber-700 dark:bg-amber-900/50 dark:text-amber-300',
    },
    emerald: {
      active: 'bg-emerald-500 text-white',
      inactive: 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800',
      badge: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/50 dark:text-emerald-300',
    },
  };

  return (
    <button
      onClick={onClick}
      className={cn(
        "flex-1 flex items-center justify-center gap-2 px-3 py-3 text-sm font-medium transition-all duration-200 rounded-lg",
        active ? colorClasses[color].active : colorClasses[color].inactive
      )}
    >
      {label}
      <span className={cn(
        "px-2 py-0.5 rounded-full text-xs font-semibold",
        active ? "bg-white/20 text-white" : colorClasses[color].badge
      )}>
        {count}
      </span>
    </button>
  );
}

export default function LogPage() {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<TabType>('running');
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);

  const runningTasks = useMemo(() => getRunningTasks(), []);
  const waitingTasks = useMemo(() => getWaitingTasks(), []);
  const completedTasks = useMemo(() => getCompletedTasks(), []);

  const currentTasks = useMemo(() => {
    switch (activeTab) {
      case 'running': return runningTasks;
      case 'waiting': return waitingTasks;
      case 'completed': return completedTasks;
      default: return runningTasks;
    }
  }, [activeTab, runningTasks, waitingTasks, completedTasks]);

  const handleTaskClick = (taskId: string) => {
    setSelectedTaskId(taskId);
    navigate(`/task/${taskId}`);
  };

  const onlineAgents = mockAgents.filter(a => a.status !== 'offline').length;
  const busyAgents = mockAgents.filter(a => a.status === 'busy').length;

  return (
    <div className="min-h-screen bg-white dark:bg-slate-950">
      {/* Header */}
      <header className="bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 sticky top-0 z-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-3">
              <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-gradient-to-br from-violet-500 to-purple-600 shadow-lg shadow-violet-500/20">
                <Terminal className="h-5 w-5 text-white" />
              </div>
              <div>
                <h1 className="text-xl font-bold text-slate-900 dark:text-white">
                  Nexus CI
                </h1>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  Agent Workflow Monitor
                </p>
              </div>
            </div>

            {/* Stats */}
            <div className="flex items-center gap-6">
              <div className="flex items-center gap-2">
                <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-50 dark:bg-emerald-900/20">
                  <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></div>
                  <span className="text-sm font-medium text-emerald-700 dark:text-emerald-400">
                    {onlineAgents} Agents Online
                  </span>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-50 dark:bg-blue-900/20">
                  <Loader2 className="h-3.5 w-3.5 text-blue-500 animate-spin" />
                  <span className="text-sm font-medium text-blue-700 dark:text-blue-400">
                    {busyAgents} Busy
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto">
        <div className="flex h-[calc(100vh-64px)]">
          {/* Left Sidebar */}
          <aside className="w-full max-w-md border-r border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50 flex flex-col">
            {/* Tabs */}
            <div className="p-4 border-b border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
              <div className="flex gap-2">
                <TabButton
                  active={activeTab === 'running'}
                  onClick={() => setActiveTab('running')}
                  label="RUNNING"
                  count={runningTasks.length}
                  color="blue"
                />
                <TabButton
                  active={activeTab === 'waiting'}
                  onClick={() => setActiveTab('waiting')}
                  label="WAITING"
                  count={waitingTasks.length}
                  color="amber"
                />
                <TabButton
                  active={activeTab === 'completed'}
                  onClick={() => setActiveTab('completed')}
                  label="COMPLETED"
                  count={completedTasks.length}
                  color="emerald"
                />
              </div>
            </div>

            {/* Task List */}
            <ScrollArea className="flex-1">
              {currentTasks.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-16 px-4 text-center">
                  <div className="w-16 h-16 rounded-full bg-slate-100 dark:bg-slate-800 flex items-center justify-center mb-4">
                    {activeTab === 'running' && <Circle className="h-8 w-8 text-slate-400" />}
                    {activeTab === 'waiting' && <Clock className="h-8 w-8 text-slate-400" />}
                    {activeTab === 'completed' && <CheckCircle className="h-8 w-8 text-slate-400" />}
                  </div>
                  <h3 className="text-sm font-medium text-slate-900 dark:text-slate-100 mb-1">
                    No {activeTab} tasks
                  </h3>
                  <p className="text-xs text-slate-500 dark:text-slate-400">
                    {activeTab === 'running' && "All agents are currently idle or waiting"}
                    {activeTab === 'waiting' && "No tasks are queued at the moment"}
                    {activeTab === 'completed' && "No tasks have been completed yet"}
                  </p>
                </div>
              ) : (
                <div className="divide-y divide-slate-200 dark:divide-slate-800">
                  {currentTasks.map((task) => (
                    <TaskListItem
                      key={task.id}
                      task={task}
                      isSelected={selectedTaskId === task.id}
                      onClick={() => handleTaskClick(task.id)}
                    />
                  ))}
                </div>
              )}
            </ScrollArea>

            {/* Footer */}
            <div className="p-3 border-t border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
              <div className="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400">
                <span>{currentTasks.length} tasks</span>
                <span className="flex items-center gap-1">
                  <Calendar className="h-3 w-3" />
                  Updated {formatRelativeTime(new Date().toISOString())}
                </span>
              </div>
            </div>
          </aside>

          {/* Right Content Area - Empty State */}
          <main className="flex-1 bg-slate-50/30 dark:bg-slate-950/30 flex items-center justify-center p-8">
            <div className="text-center max-w-md">
              <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-slate-100 to-slate-200 dark:from-slate-800 dark:to-slate-700 flex items-center justify-center mx-auto mb-6 shadow-inner">
                <Activity className="h-10 w-10 text-slate-400 dark:text-slate-500" />
              </div>
              <h2 className="text-xl font-semibold text-slate-900 dark:text-white mb-2">
                Select a task to view details
              </h2>
              <p className="text-sm text-slate-500 dark:text-slate-400 leading-relaxed">
                Click on any task from the sidebar to view real-time logs,
                execution details, and agent information.
              </p>
              <div className="mt-6 flex items-center justify-center gap-4 text-xs text-slate-400">
                <span className="flex items-center gap-1">
                  <Circle className="h-3 w-3 text-blue-500 fill-blue-500" />
                  Running
                </span>
                <span className="flex items-center gap-1">
                  <Clock className="h-3 w-3 text-amber-500" />
                  Waiting
                </span>
                <span className="flex items-center gap-1">
                  <CheckCircle className="h-3 w-3 text-emerald-500" />
                  Completed
                </span>
              </div>
            </div>
          </main>
        </div>
      </div>
    </div>
  );
}
