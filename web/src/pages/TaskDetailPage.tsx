import { useEffect, useMemo, useRef, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  CheckCircle,
  XCircle,
  AlertCircle,
  Clock,
  Circle,
  Loader2,
  Terminal,
  GitBranch,
  Server,
  Calendar,
  Timer,
  Copy,
  Download,
  RotateCcw,
  Play,
  FileCode,
  Hash,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Badge } from '@/components/ui/badge';
import { getTaskById, getAgentByTaskId } from '@/data/mockWorkflows';
import type { TaskStatus, LogEntry } from '@/types/agent';

const statusConfig: Record<TaskStatus, {
  icon: React.ReactNode;
  color: string;
  bgColor: string;
  borderColor: string;
  label: string;
}> = {
  running: {
    icon: <Loader2 className="h-5 w-5 animate-spin" />,
    color: 'text-blue-500',
    bgColor: 'bg-blue-50 dark:bg-blue-900/20',
    borderColor: 'border-blue-200 dark:border-blue-800',
    label: 'Running',
  },
  waiting: {
    icon: <Clock className="h-5 w-5" />,
    color: 'text-amber-500',
    bgColor: 'bg-amber-50 dark:bg-amber-900/20',
    borderColor: 'border-amber-200 dark:border-amber-800',
    label: 'Waiting',
  },
  completed: {
    icon: <CheckCircle className="h-5 w-5" />,
    color: 'text-emerald-500',
    bgColor: 'bg-emerald-50 dark:bg-emerald-900/20',
    borderColor: 'border-emerald-200 dark:border-emerald-800',
    label: 'Completed',
  },
  failed: {
    icon: <XCircle className="h-5 w-5" />,
    color: 'text-red-500',
    bgColor: 'bg-red-50 dark:bg-red-900/20',
    borderColor: 'border-red-200 dark:border-red-800',
    label: 'Failed',
  },
  error: {
    icon: <AlertCircle className="h-5 w-5" />,
    color: 'text-orange-500',
    bgColor: 'bg-orange-50 dark:bg-orange-900/20',
    borderColor: 'border-orange-200 dark:border-orange-800',
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

function formatTime(isoString: string): string {
  return new Date(isoString).toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

interface LogLineProps {
  log: LogEntry;
  index: number;
}

function LogLine({ log, index }: LogLineProps) {
  const levelColors = {
    info: 'text-blue-400',
    warning: 'text-amber-400',
    error: 'text-red-400',
    success: 'text-emerald-400',
  };

  return (
    <div className="flex gap-3 py-1 font-mono text-sm leading-relaxed hover:bg-white/5">
      <span className="text-slate-600 select-none w-12 text-right shrink-0">
        {index + 1}
      </span>
      <span className="text-slate-500 shrink-0">
        {formatTime(log.timestamp)}
      </span>
      <span className={cn("uppercase text-xs font-bold shrink-0 w-16", levelColors[log.level])}>
        {log.level}
      </span>
      <span className="text-slate-300 whitespace-pre-wrap break-all">
        {log.message}
      </span>
    </div>
  );
}

interface StatCardProps {
  label: string;
  value: string;
  icon: React.ReactNode;
  color?: 'default' | 'blue' | 'emerald' | 'amber' | 'red';
}

function StatCard({ label, value, icon, color = 'default' }: StatCardProps) {
  const colorClasses = {
    default: 'bg-slate-50 dark:bg-slate-800 border-slate-200 dark:border-slate-700',
    blue: 'bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800',
    emerald: 'bg-emerald-50 dark:bg-emerald-900/20 border-emerald-200 dark:border-emerald-800',
    amber: 'bg-amber-50 dark:bg-amber-900/20 border-amber-200 dark:border-amber-800',
    red: 'bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800',
  };

  return (
    <div className={cn("flex items-center gap-3 p-4 rounded-xl border", colorClasses[color])}>
      <div className="p-2 rounded-lg bg-white dark:bg-slate-700 shadow-sm">
        {icon}
      </div>
      <div>
        <p className="text-xs text-slate-500 dark:text-slate-400 uppercase tracking-wide font-medium">
          {label}
        </p>
        <p className="text-lg font-semibold text-slate-900 dark:text-white">
          {value}
        </p>
      </div>
    </div>
  );
}

export default function TaskDetailPage() {
  const { taskId } = useParams<{ taskId: string }>();
  const navigate = useNavigate();
  const scrollRef = useRef<HTMLDivElement>(null);
  const [autoScroll, setAutoScroll] = useState(true);

  const task = useMemo(() => taskId ? getTaskById(taskId) : undefined, [taskId]);
  const agent = useMemo(() => taskId ? getAgentByTaskId(taskId) : undefined, [taskId]);

  // Auto-scroll to bottom for running tasks
  useEffect(() => {
    if (autoScroll && scrollRef.current && task?.status === 'running') {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [task?.logs, autoScroll, task?.status]);

  // Handle scroll event to disable auto-scroll if user scrolls up
  const handleScroll = () => {
    if (scrollRef.current) {
      const { scrollTop, scrollHeight, clientHeight } = scrollRef.current;
      const isAtBottom = scrollHeight - scrollTop - clientHeight < 50;
      setAutoScroll(isAtBottom);
    }
  };

  if (!task) {
    return (
      <div className="min-h-screen bg-slate-50 dark:bg-slate-950 flex items-center justify-center">
        <div className="text-center">
          <div className="w-16 h-16 rounded-full bg-slate-200 dark:bg-slate-800 flex items-center justify-center mx-auto mb-4">
            <AlertCircle className="h-8 w-8 text-slate-400" />
          </div>
          <h2 className="text-xl font-semibold text-slate-900 dark:text-white mb-2">
            Task not found
          </h2>
          <p className="text-slate-500 dark:text-slate-400 mb-4">
            The task you're looking for doesn't exist or has been removed.
          </p>
          <button
            onClick={() => navigate('/')}
            className="inline-flex items-center gap-2 px-4 py-2 bg-blue-500 hover:bg-blue-600 text-white rounded-lg font-medium transition-colors"
          >
            <ArrowLeft className="h-4 w-4" />
            Go back
          </button>
        </div>
      </div>
    );
  }

  const config = statusConfig[task.status];
  const elapsed = task.startTime
    ? Math.floor((Date.now() - new Date(task.startTime).getTime()) / 1000)
    : 0;

  const handleCopyLogs = () => {
    const logText = task.logs
      .map(log => `[${formatTime(log.timestamp)}] [${log.level.toUpperCase()}] ${log.message}`)
      .join('\n');
    navigator.clipboard.writeText(logText);
  };

  const handleDownloadLogs = () => {
    const logText = task.logs
      .map(log => `[${formatTime(log.timestamp)}] [${log.level.toUpperCase()}] ${log.message}`)
      .join('\n');
    const blob = new Blob([logText], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${task.id}-logs.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="min-h-screen bg-white dark:bg-slate-950">
      {/* Header */}
      <header className="bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 sticky top-0 z-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-4">
              <button
                onClick={() => navigate('/')}
                className="p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
              >
                <ArrowLeft className="h-5 w-5 text-slate-600 dark:text-slate-400" />
              </button>
              <div className="flex items-center gap-3">
                <div className={cn("p-2 rounded-lg", config.bgColor)}>
                  {config.icon}
                </div>
                <div>
                  <h1 className="text-lg font-semibold text-slate-900 dark:text-white">
                    {task.title}
                  </h1>
                  <div className="flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400">
                    <span className="flex items-center gap-1">
                      <Server className="h-3.5 w-3.5" />
                      {task.agentName}
                    </span>
                    <span>•</span>
                    <Badge variant="outline" className={cn("text-xs", config.color)}>
                      {config.label}
                    </Badge>
                  </div>
                </div>
              </div>
            </div>

            {/* Actions */}
            <div className="flex items-center gap-2">
              <button
                onClick={handleCopyLogs}
                className="p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-600 dark:text-slate-400 transition-colors"
                title="Copy logs"
              >
                <Copy className="h-4 w-4" />
              </button>
              <button
                onClick={handleDownloadLogs}
                className="p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-600 dark:text-slate-400 transition-colors"
                title="Download logs"
              >
                <Download className="h-4 w-4" />
              </button>
              {task.status === 'failed' || task.status === 'error' ? (
                <button className="flex items-center gap-2 px-4 py-2 bg-red-500 hover:bg-red-600 text-white rounded-lg font-medium transition-colors">
                  <RotateCcw className="h-4 w-4" />
                  Retry
                </button>
              ) : task.status === 'completed' ? (
                <button className="flex items-center gap-2 px-4 py-2 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 rounded-lg font-medium transition-colors">
                  <Play className="h-4 w-4" />
                  Run Again
                </button>
              ) : null}
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto">
        <div className="flex h-[calc(100vh-64px)]">
          {/* Left Panel - Info */}
          <aside className="w-80 border-r border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50 overflow-y-auto">
            <div className="p-6 space-y-6">
              {/* Status Card */}
              <div className={cn("p-4 rounded-xl border", config.bgColor, config.borderColor)}>
                <div className="flex items-center gap-3">
                  {task.status === 'running' ? (
                    <div className="relative">
                      <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-blue-400 opacity-30"></span>
                      <span className="relative inline-flex rounded-full p-2 bg-blue-100 dark:bg-blue-900/30">
                        <Circle className="h-5 w-5 text-blue-500 fill-blue-500" />
                      </span>
                    </div>
                  ) : (
                    <span className={cn("inline-flex rounded-full p-2", config.color.replace('text-', 'bg-').replace('500', '100'))}>
                      {config.icon}
                    </span>
                  )}
                  <div>
                    <p className="text-sm font-medium text-slate-900 dark:text-white">
                      {config.label}
                    </p>
                    {task.status === 'running' && (
                      <p className="text-xs text-blue-600 dark:text-blue-400">
                        {formatDuration(elapsed)}
                      </p>
                    )}
                  </div>
                </div>
              </div>

              {/* Stats Grid */}
              <div className="grid grid-cols-1 gap-3">
                {task.duration && (
                  <StatCard
                    label="Duration"
                    value={formatDuration(task.duration)}
                    icon={<Timer className="h-4 w-4 text-slate-600" />}
                    color="default"
                  />
                )}
                {task.startTime && (
                  <StatCard
                    label="Started"
                    value={formatTime(task.startTime)}
                    icon={<Calendar className="h-4 w-4 text-blue-600" />}
                    color="blue"
                  />
                )}
                {task.endTime && (
                  <StatCard
                    label="Ended"
                    value={formatTime(task.endTime)}
                    icon={<CheckCircle className="h-4 w-4 text-emerald-600" />}
                    color="emerald"
                  />
                )}
              </div>

              {/* Metadata */}
              {task.metadata && (
                <div className="space-y-4">
                  <h3 className="text-sm font-semibold text-slate-900 dark:text-white uppercase tracking-wide">
                    Metadata
                  </h3>
                  <div className="space-y-3">
                    {task.metadata.repository && (
                      <div className="flex items-center justify-between p-3 bg-white dark:bg-slate-800 rounded-lg border border-slate-200 dark:border-slate-700">
                        <span className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-400">
                          <FileCode className="h-4 w-4" />
                          Repository
                        </span>
                        <span className="text-sm font-medium text-slate-900 dark:text-white">
                          {task.metadata.repository}
                        </span>
                      </div>
                    )}
                    {task.metadata.branch && (
                      <div className="flex items-center justify-between p-3 bg-white dark:bg-slate-800 rounded-lg border border-slate-200 dark:border-slate-700">
                        <span className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-400">
                          <GitBranch className="h-4 w-4" />
                          Branch
                        </span>
                        <span className="text-sm font-medium text-slate-900 dark:text-white">
                          {task.metadata.branch}
                        </span>
                      </div>
                    )}
                    {task.metadata.commit && (
                      <div className="flex items-center justify-between p-3 bg-white dark:bg-slate-800 rounded-lg border border-slate-200 dark:border-slate-700">
                        <span className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-400">
                          <Hash className="h-4 w-4" />
                          Commit
                        </span>
                        <span className="text-sm font-mono text-slate-900 dark:text-white">
                          {task.metadata.commit.slice(0, 7)}
                        </span>
                      </div>
                    )}
                    {task.metadata.command && (
                      <div className="p-3 bg-white dark:bg-slate-800 rounded-lg border border-slate-200 dark:border-slate-700">
                        <span className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-400 mb-2">
                          <Terminal className="h-4 w-4" />
                          Command
                        </span>
                        <code className="block text-xs font-mono bg-slate-100 dark:bg-slate-900 p-2 rounded text-slate-700 dark:text-slate-300">
                          {task.metadata.command}
                        </code>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Agent Info */}
              {agent && (
                <div className="space-y-4">
                  <h3 className="text-sm font-semibold text-slate-900 dark:text-white uppercase tracking-wide">
                    Agent
                  </h3>
                  <div className="p-4 bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700">
                    <div className="flex items-center gap-3 mb-3">
                      <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center">
                        <Server className="h-5 w-5 text-white" />
                      </div>
                      <div>
                        <p className="font-medium text-slate-900 dark:text-white">
                          {agent.name}
                        </p>
                        <div className="flex items-center gap-2">
                          <div className={cn(
                            "w-2 h-2 rounded-full",
                            agent.status === 'online' && "bg-emerald-500",
                            agent.status === 'busy' && "bg-blue-500",
                            agent.status === 'offline' && "bg-slate-400"
                          )} />
                          <span className="text-xs text-slate-500 dark:text-slate-400 capitalize">
                            {agent.status}
                          </span>
                        </div>
                      </div>
                    </div>
                    <div className="grid grid-cols-3 gap-2 text-center">
                      <div className="p-2 bg-slate-50 dark:bg-slate-900 rounded-lg">
                        <p className="text-lg font-semibold text-slate-900 dark:text-white">
                          {agent.completedTasks.length}
                        </p>
                        <p className="text-xs text-slate-500">Completed</p>
                      </div>
                      <div className="p-2 bg-slate-50 dark:bg-slate-900 rounded-lg">
                        <p className="text-lg font-semibold text-blue-600 dark:text-blue-400">
                          {agent.taskQueue.length}
                        </p>
                        <p className="text-xs text-slate-500">Queued</p>
                      </div>
                      <div className="p-2 bg-slate-50 dark:bg-slate-900 rounded-lg">
                        <p className="text-lg font-semibold text-slate-900 dark:text-white">
                          {agent.completedTasks.length + agent.taskQueue.length + (agent.currentTask ? 1 : 0)}
                        </p>
                        <p className="text-xs text-slate-500">Total</p>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* Error Display */}
              {task.error && (
                <div className="p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-xl">
                  <div className="flex items-center gap-2 text-red-700 dark:text-red-400 mb-2">
                    <AlertCircle className="h-4 w-4" />
                    <span className="font-medium text-sm">Error</span>
                  </div>
                  <p className="text-sm text-red-600 dark:text-red-300 font-mono">
                    {task.error}
                  </p>
                </div>
              )}
            </div>
          </aside>

          {/* Right Panel - Logs */}
          <main className="flex-1 flex flex-col bg-slate-950">
            {/* Logs Header */}
            <div className="flex items-center justify-between px-4 py-3 bg-slate-900 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <Terminal className="h-4 w-4 text-slate-400" />
                <span className="text-sm font-medium text-slate-300">Console Output</span>
                <Badge variant="outline" className="text-xs border-slate-700 text-slate-400">
                  {task.logs.length} lines
                </Badge>
              </div>
              <div className="flex items-center gap-2">
                {task.status === 'running' && (
                  <div className="flex items-center gap-2 text-xs text-slate-400">
                    <div className={cn("w-2 h-2 rounded-full", autoScroll ? "bg-emerald-500" : "bg-slate-500")} />
                    Auto-scroll {autoScroll ? 'on' : 'off'}
                  </div>
                )}
              </div>
            </div>

            {/* Logs Content */}
            <ScrollArea className="flex-1">
              <div
                ref={scrollRef}
                onScroll={handleScroll}
                className="p-4 min-h-full"
              >
                {task.logs.length === 0 ? (
                  <div className="flex flex-col items-center justify-center h-full text-center py-16">
                    <div className="w-12 h-12 rounded-full bg-slate-800 flex items-center justify-center mb-4">
                      <Terminal className="h-6 w-6 text-slate-600" />
                    </div>
                    <p className="text-slate-500 text-sm">No logs available yet</p>
                  </div>
                ) : (
                  <div className="space-y-0.5">
                    {task.logs.map((log, index) => (
                      <LogLine key={index} log={log} index={index} />
                    ))}
                    {task.status === 'running' && (
                      <div className="flex items-center gap-2 py-2 text-slate-500">
                        <Loader2 className="h-4 w-4 animate-spin" />
                        <span className="text-sm">Waiting for more output...</span>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </ScrollArea>
          </main>
        </div>
      </div>
    </div>
  );
}
