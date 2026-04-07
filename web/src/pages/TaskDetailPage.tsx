import { useEffect, useRef, useState, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Clock,
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
  ChevronRight,
  Zap,
  Check,
  WifiOff,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { getTaskById, getAgentByTaskId } from '@/data/mockWorkflows';
import type { TaskStatus, LogEntry } from '@/types/agent';

// ─── Status configuration ─────────────────────────────────────────────────────

const statusConfig: Record<
  TaskStatus,
  {
    icon: React.ReactNode;
    dotColor: string;
    textColor: string;
    bgColor: string;
    borderColor: string;
    barColor: string;
    label: string;
  }
> = {
  running: {
    icon: <Loader2 className="h-4 w-4 animate-spin" />,
    dotColor: 'bg-amber-400',
    textColor: 'text-amber-700',
    bgColor: 'bg-amber-50',
    borderColor: 'border-amber-200',
    barColor: 'bg-amber-400',
    label: 'Running',
  },
  waiting: {
    icon: <Clock className="h-4 w-4" />,
    dotColor: 'bg-slate-400',
    textColor: 'text-slate-600',
    bgColor: 'bg-slate-50',
    borderColor: 'border-slate-200',
    barColor: 'bg-slate-400',
    label: 'Waiting',
  },
  completed: {
    icon: <CheckCircle2 className="h-4 w-4" />,
    dotColor: 'bg-emerald-500',
    textColor: 'text-emerald-700',
    bgColor: 'bg-emerald-50',
    borderColor: 'border-emerald-200',
    barColor: 'bg-emerald-500',
    label: 'Passed',
  },
  failed: {
    icon: <XCircle className="h-4 w-4" />,
    dotColor: 'bg-red-500',
    textColor: 'text-red-700',
    bgColor: 'bg-red-50',
    borderColor: 'border-red-200',
    barColor: 'bg-red-500',
    label: 'Failed',
  },
  error: {
    icon: <AlertCircle className="h-4 w-4" />,
    dotColor: 'bg-orange-500',
    textColor: 'text-orange-700',
    bgColor: 'bg-orange-50',
    borderColor: 'border-orange-200',
    barColor: 'bg-orange-500',
    label: 'Error',
  },
};

// ─── Helpers ──────────────────────────────────────────────────────────────────

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  const remaining = seconds % 60;
  if (minutes < 60) return remaining > 0 ? `${minutes}m ${remaining}s` : `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  const rem = minutes % 60;
  return rem > 0 ? `${hours}h ${rem}m` : `${hours}h`;
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

// ─── Log line component ───────────────────────────────────────────────────────

const logLevelConfig: Record<
  LogEntry['level'],
  { text: string; bg: string; label: string }
> = {
  info:    { text: 'text-sky-400',     bg: 'bg-sky-950/30',     label: 'INFO ' },
  warning: { text: 'text-amber-400',   bg: 'bg-amber-950/30',   label: 'WARN ' },
  error:   { text: 'text-red-400',     bg: 'bg-red-950/30',     label: 'ERROR' },
  success: { text: 'text-emerald-400', bg: 'bg-emerald-950/30', label: ' OK  ' },
};

interface LogLineProps {
  log: LogEntry;
  index: number;
}

function LogLine({ log, index }: LogLineProps) {
  const lc = logLevelConfig[log.level];
  return (
    <div
      className={cn(
        'group flex gap-0 font-mono text-[13px] leading-6 hover:bg-white/[0.04] rounded',
        log.level === 'error' && 'bg-red-950/20',
        log.level === 'warning' && 'bg-amber-950/10',
      )}
    >
      {/* Line number */}
      <span className="select-none text-slate-600 text-right w-10 shrink-0 pr-3 pt-px tabular-nums text-xs">
        {index + 1}
      </span>

      {/* Timestamp */}
      <span className="text-slate-500 shrink-0 pr-3 text-xs pt-px tabular-nums">
        {formatTime(log.timestamp)}
      </span>

      {/* Level badge */}
      <span className={cn(
        'shrink-0 mr-3 px-1 rounded text-xs font-bold tracking-widest pt-px tabular-nums',
        lc.text
      )}>
        {lc.label}
      </span>

      {/* Message */}
      <span className={cn(
        'flex-1 min-w-0 whitespace-pre-wrap break-all pr-4',
        log.level === 'error'   && 'text-red-300',
        log.level === 'warning' && 'text-amber-200',
        log.level === 'success' && 'text-emerald-300',
        log.level === 'info'    && 'text-slate-300',
      )}>
        {log.message}
      </span>
    </div>
  );
}

// ─── Metadata row ─────────────────────────────────────────────────────────────

function MetaRow({
  icon,
  label,
  value,
  mono = false,
}: {
  icon: React.ReactNode;
  label: string;
  value: React.ReactNode;
  mono?: boolean;
}) {
  return (
    <div className="flex items-start justify-between gap-3 py-2.5 border-b border-slate-100 last:border-0">
      <span className="flex items-center gap-2 text-xs text-slate-500 shrink-0">
        <span className="text-slate-400">{icon}</span>
        {label}
      </span>
      <span className={cn(
        'text-xs text-slate-800 font-medium text-right',
        mono && 'font-mono'
      )}>
        {value}
      </span>
    </div>
  );
}

// ─── Copy button with feedback ────────────────────────────────────────────────

function CopyButton({ text, title }: { text: string; title: string }) {
  const [copied, setCopied] = useState(false);
  const handleCopy = async () => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  };
  return (
    <button
      onClick={handleCopy}
      title={title}
      className="p-1.5 rounded-md text-slate-500 hover:text-slate-200 hover:bg-white/10 transition-colors cursor-pointer"
    >
      {copied ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
    </button>
  );
}

// ─── TaskDetailPage ───────────────────────────────────────────────────────────

export default function TaskDetailPage() {
  const { taskId } = useParams<{ taskId: string }>();
  const navigate = useNavigate();
  const logEndRef = useRef<HTMLDivElement>(null);
  const logContainerRef = useRef<HTMLDivElement>(null);
  const [autoScroll, setAutoScroll] = useState(true);
  const [elapsed, setElapsed] = useState(0);

  const task  = useMemo(() => taskId ? getTaskById(taskId) : undefined, [taskId]);
  const agent = useMemo(() => taskId ? getAgentByTaskId(taskId) : undefined, [taskId]);

  // Live elapsed timer for running tasks
  useEffect(() => {
    if (task?.status !== 'running' || !task.startTime) return;
    const tick = () =>
      setElapsed(Math.floor((Date.now() - new Date(task.startTime!).getTime()) / 1000));
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [task]);

  // Auto-scroll to bottom
  useEffect(() => {
    if (autoScroll && logEndRef.current) {
      logEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [task?.logs, autoScroll]);

  const handleScroll = () => {
    const el = logContainerRef.current;
    if (!el) return;
    const { scrollTop, scrollHeight, clientHeight } = el;
    setAutoScroll(scrollHeight - scrollTop - clientHeight < 80);
  };

  // ── Not found ───────────────────────────────────────────────────────────
  if (!task) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center p-6">
        <div className="text-center max-w-sm">
          <div className="w-16 h-16 rounded-2xl bg-white border border-slate-200 shadow-sm flex items-center justify-center mx-auto mb-5">
            <AlertCircle className="h-8 w-8 text-slate-300" />
          </div>
          <h2 className="text-lg font-semibold text-slate-800 mb-2">Task not found</h2>
          <p className="text-sm text-slate-500 mb-5">
            The task you're looking for doesn't exist or has been removed.
          </p>
          <button
            onClick={() => navigate('/')}
            className="inline-flex items-center gap-2 px-4 py-2 bg-violet-600 hover:bg-violet-700 text-white rounded-lg text-sm font-medium transition-colors cursor-pointer shadow-sm"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to agents
          </button>
        </div>
      </div>
    );
  }

  const cfg = statusConfig[task.status];

  const logText = task.logs
    .map(l => `[${formatTime(l.timestamp)}] [${l.level.toUpperCase().padEnd(5)}] ${l.message}`)
    .join('\n');

  const handleDownload = () => {
    const blob = new Blob([logText], { type: 'text/plain' });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href = url;
    a.download = `${task.id}-logs.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">

      {/* ── Top navigation bar ──────────────────────────────────────────── */}
      <header className="sticky top-0 z-30 bg-white border-b border-slate-200 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6">
          <div className="flex items-center gap-4 h-12">

            {/* Brand + back */}
            <div className="flex items-center gap-2 flex-shrink-0">
              <div className="flex items-center justify-center w-6 h-6 rounded-md bg-violet-600">
                <Zap className="h-3.5 w-3.5 text-white" />
              </div>
              <span className="text-sm font-semibold text-slate-800 hidden sm:inline">Nexus CI</span>
            </div>

            {/* Breadcrumb */}
            <div className="flex items-center gap-1.5 text-sm min-w-0">
              <button
                onClick={() => navigate('/')}
                className="text-slate-500 hover:text-violet-600 transition-colors cursor-pointer flex-shrink-0 flex items-center gap-1"
              >
                <ArrowLeft className="h-3.5 w-3.5" />
                Agents
              </button>
              <ChevronRight className="h-3.5 w-3.5 text-slate-300 flex-shrink-0" />
              {agent && (
                <>
                  <button
                    onClick={() => navigate('/')}
                    className="text-slate-500 hover:text-violet-600 transition-colors cursor-pointer flex-shrink-0 truncate max-w-32"
                  >
                    {agent.name}
                  </button>
                  <ChevronRight className="h-3.5 w-3.5 text-slate-300 flex-shrink-0" />
                </>
              )}
              <span className="text-slate-800 font-medium truncate">{task.title}</span>
            </div>

            {/* Spacer */}
            <div className="flex-1" />

            {/* Action buttons */}
            <div className="flex items-center gap-1.5 flex-shrink-0">
              <CopyButton text={logText} title="Copy logs" />
              <button
                onClick={handleDownload}
                title="Download logs"
                className="p-1.5 rounded-md text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors cursor-pointer"
              >
                <Download className="h-3.5 w-3.5" />
              </button>

              {(task.status === 'failed' || task.status === 'error') && (
                <button className="flex items-center gap-1.5 px-3 py-1.5 bg-red-600 hover:bg-red-700 text-white rounded-lg text-xs font-medium transition-colors cursor-pointer shadow-sm">
                  <RotateCcw className="h-3.5 w-3.5" />
                  Retry
                </button>
              )}
              {task.status === 'completed' && (
                <button className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-800 hover:bg-slate-900 text-white rounded-lg text-xs font-medium transition-colors cursor-pointer shadow-sm">
                  <Play className="h-3.5 w-3.5" />
                  Run again
                </button>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* ── Status banner ────────────────────────────────────────────────── */}
      <div className={cn('border-b', cfg.bgColor, cfg.borderColor)}>
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-4">
          <div className="flex items-center gap-4 flex-wrap">

            {/* Status badge */}
            <span className={cn(
              'inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-sm font-semibold border',
              cfg.bgColor, cfg.textColor, cfg.borderColor
            )}>
              {task.status === 'running' ? (
                <span className="relative flex h-2.5 w-2.5">
                  <span className={cn('animate-ping absolute inset-0 rounded-full opacity-60', cfg.dotColor)} />
                  <span className={cn('relative rounded-full h-2.5 w-2.5', cfg.dotColor)} />
                </span>
              ) : (
                <span className={cn('rounded-full h-2.5 w-2.5', cfg.dotColor)} />
              )}
              {cfg.label}
            </span>

            {/* Task title */}
            <h1 className={cn('text-base font-semibold', cfg.textColor)}>
              {task.title}
            </h1>

            {/* Elapsed / duration */}
            {task.status === 'running' && (
              <span className="flex items-center gap-1.5 text-sm text-amber-600">
                <Timer className="h-3.5 w-3.5" />
                {formatDuration(elapsed)} elapsed
              </span>
            )}
            {task.duration && task.status !== 'running' && (
              <span className="flex items-center gap-1.5 text-sm text-slate-500">
                <Timer className="h-3.5 w-3.5" />
                {formatDuration(task.duration)}
              </span>
            )}
          </div>
        </div>
      </div>

      {/* ── Two-column layout ─────────────────────────────────────────────── */}
      <div className="flex-1 flex overflow-hidden max-w-7xl mx-auto w-full">

        {/* ── Left sidebar ──────────────────────────────────────────────── */}
        <aside className="w-72 lg:w-80 border-r border-slate-200 bg-white overflow-y-auto flex-shrink-0">
          <div className="p-5 space-y-5">

            {/* ── Timing section ────────────────────────────────────────── */}
            <section>
              <h2 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">
                Timing
              </h2>
              <div className="rounded-lg border border-slate-200 bg-slate-50/50 overflow-hidden">
                {task.startTime && (
                  <MetaRow
                    icon={<Calendar className="h-3.5 w-3.5" />}
                    label="Started"
                    value={
                      <span>
                        <span className="block">{formatTime(task.startTime)}</span>
                        <span className="text-slate-400 font-normal">{formatDate(task.startTime)}</span>
                      </span>
                    }
                  />
                )}
                {task.endTime && (
                  <MetaRow
                    icon={<CheckCircle2 className="h-3.5 w-3.5" />}
                    label="Finished"
                    value={
                      <span>
                        <span className="block">{formatTime(task.endTime)}</span>
                        <span className="text-slate-400 font-normal">{formatDate(task.endTime)}</span>
                      </span>
                    }
                  />
                )}
                {task.duration && (
                  <MetaRow
                    icon={<Timer className="h-3.5 w-3.5" />}
                    label="Duration"
                    value={formatDuration(task.duration)}
                  />
                )}
                {task.status === 'running' && (
                  <MetaRow
                    icon={<Timer className="h-3.5 w-3.5" />}
                    label="Elapsed"
                    value={
                      <span className="text-amber-600 font-semibold animate-pulse">
                        {formatDuration(elapsed)}
                      </span>
                    }
                  />
                )}
              </div>
            </section>

            {/* ── Build metadata ────────────────────────────────────────── */}
            {task.metadata && (
              <section>
                <h2 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">
                  Build
                </h2>
                <div className="rounded-lg border border-slate-200 bg-slate-50/50 overflow-hidden">
                  {task.metadata.repository && (
                    <MetaRow
                      icon={<FileCode className="h-3.5 w-3.5" />}
                      label="Repository"
                      value={task.metadata.repository}
                    />
                  )}
                  {task.metadata.branch && (
                    <MetaRow
                      icon={<GitBranch className="h-3.5 w-3.5" />}
                      label="Branch"
                      value={
                        <span className="px-1.5 py-0.5 rounded bg-slate-100 font-mono text-slate-700">
                          {task.metadata.branch}
                        </span>
                      }
                    />
                  )}
                  {task.metadata.commit && (
                    <MetaRow
                      icon={<Hash className="h-3.5 w-3.5" />}
                      label="Commit"
                      value={
                        <span className="font-mono text-slate-700">
                          {task.metadata.commit.slice(0, 7)}
                        </span>
                      }
                      mono
                    />
                  )}
                  {task.metadata.command && (
                    <div className="px-3 py-2.5 border-t border-slate-100">
                      <div className="flex items-center gap-2 text-xs text-slate-500 mb-1.5">
                        <Terminal className="h-3.5 w-3.5 text-slate-400" />
                        Command
                      </div>
                      <code className="block text-xs font-mono bg-slate-900 text-emerald-400 p-2.5 rounded-lg break-all">
                        {task.metadata.command}
                      </code>
                    </div>
                  )}
                </div>
              </section>
            )}

            {/* ── Agent info ────────────────────────────────────────────── */}
            {agent && (
              <section>
                <h2 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">
                  Agent
                </h2>
                <div className="rounded-lg border border-slate-200 bg-white overflow-hidden">
                  <div className="p-3 flex items-center gap-3 border-b border-slate-100">
                    <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-violet-500 to-violet-700 flex items-center justify-center flex-shrink-0">
                      <Server className="h-4 w-4 text-white" />
                    </div>
                    <div className="min-w-0">
                      <p className="text-sm font-semibold text-slate-800 truncate">{agent.name}</p>
                      <div className="flex items-center gap-1.5 mt-0.5">
                        <span className={cn(
                          'w-1.5 h-1.5 rounded-full flex-shrink-0',
                          agent.status === 'online'  && 'bg-emerald-500',
                          agent.status === 'busy'    && 'bg-amber-400',
                          agent.status === 'offline' && 'bg-slate-300',
                        )} />
                        <span className="text-xs text-slate-500 capitalize">{agent.status}</span>
                      </div>
                    </div>
                    {agent.status === 'offline' && (
                      <WifiOff className="h-4 w-4 text-slate-300 ml-auto" />
                    )}
                  </div>
                  <div className="grid grid-cols-3 divide-x divide-slate-100">
                    {[
                      { label: 'Done', value: agent.completedTasks.length, color: 'text-emerald-600' },
                      { label: 'Queued', value: agent.taskQueue.length,    color: 'text-amber-600'   },
                      {
                        label: 'Total',
                        value: agent.completedTasks.length + agent.taskQueue.length + (agent.currentTask ? 1 : 0),
                        color: 'text-slate-700',
                      },
                    ].map(({ label, value, color }) => (
                      <div key={label} className="py-3 text-center">
                        <p className={cn('text-lg font-bold tabular-nums', color)}>{value}</p>
                        <p className="text-xs text-slate-400 mt-0.5">{label}</p>
                      </div>
                    ))}
                  </div>
                </div>
              </section>
            )}

            {/* ── Error display ─────────────────────────────────────────── */}
            {task.error && (
              <section>
                <h2 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">
                  Error
                </h2>
                <div className="rounded-lg border border-red-200 bg-red-50 p-3">
                  <div className="flex items-center gap-2 text-red-700 mb-2">
                    <AlertCircle className="h-4 w-4 flex-shrink-0" />
                    <span className="text-xs font-semibold">Build error</span>
                  </div>
                  <p className="text-xs text-red-800 font-mono leading-relaxed break-all">
                    {task.error}
                  </p>
                </div>
              </section>
            )}
          </div>
        </aside>

        {/* ── Log panel ──────────────────────────────────────────────────── */}
        <main className="flex-1 flex flex-col bg-[#0d1117] min-h-0 overflow-hidden">

          {/* Log panel header */}
          <div className="flex items-center justify-between px-4 py-2.5 bg-[#161b22] border-b border-white/[0.08] flex-shrink-0">
            <div className="flex items-center gap-2.5">
              <Terminal className="h-4 w-4 text-slate-400" />
              <span className="text-sm font-medium text-slate-300">Console Output</span>
              <span className="px-2 py-0.5 rounded-full bg-white/[0.06] text-slate-400 text-xs tabular-nums">
                {task.logs.length} lines
              </span>
            </div>
            <div className="flex items-center gap-2">
              {task.status === 'running' && (
                <span className="flex items-center gap-1.5 text-xs text-slate-400">
                  <span className={cn(
                    'w-1.5 h-1.5 rounded-full',
                    autoScroll ? 'bg-emerald-400' : 'bg-slate-500'
                  )} />
                  {autoScroll ? 'Auto-scroll on' : 'Auto-scroll off'}
                </span>
              )}
              <CopyButton text={logText} title="Copy all logs" />
              <button
                onClick={handleDownload}
                title="Download logs"
                className="p-1.5 rounded-md text-slate-500 hover:text-slate-200 hover:bg-white/10 transition-colors cursor-pointer"
              >
                <Download className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>

          {/* Log content */}
          <div
            ref={logContainerRef}
            onScroll={handleScroll}
            className="flex-1 overflow-y-auto p-3 scroll-smooth"
          >
            {task.logs.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-center py-20">
                <div className="w-12 h-12 rounded-full bg-white/[0.04] flex items-center justify-center mb-4">
                  <Terminal className="h-5 w-5 text-slate-600" />
                </div>
                <p className="text-slate-500 text-sm">No output yet</p>
              </div>
            ) : (
              <div className="space-y-0.5">
                {task.logs.map((log, i) => (
                  <LogLine key={i} log={log} index={i} />
                ))}
                {task.status === 'running' && (
                  <div className="flex items-center gap-2 py-2 pl-10 text-slate-500">
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    <span className="text-xs">Waiting for output…</span>
                  </div>
                )}
                <div ref={logEndRef} />
              </div>
            )}
          </div>
        </main>
      </div>
    </div>
  );
}
