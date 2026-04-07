import { useParams, Link } from 'react-router-dom';
import { ArrowLeft, Bot, GitBranch, AlertCircle } from 'lucide-react';
import { cn } from '@/lib/utils';
import { getTaskById } from '@/data/mockWorkflows';

const LEVEL_STYLES: Record<string, string> = {
  info:    'text-stone-500',
  success: 'text-emerald-700',
  warning: 'text-amber-700',
  error:   'text-red-600',
};

export default function TaskDetailPage() {
  const { taskId } = useParams<{ taskId: string }>();
  const task = taskId ? getTaskById(taskId) : undefined;

  if (!task) {
    return (
      <div className="min-h-screen bg-[#F2EDE4] flex flex-col items-center justify-center gap-4">
        <AlertCircle className="size-8 text-stone-300" />
        <p className="text-stone-400 text-sm">Task not found: {taskId}</p>
        <Link to="/" className="text-orange-700 text-sm hover:underline underline-offset-4">
          ← Back to overview
        </Link>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#F2EDE4]">

      {/* Header */}
      <div className="bg-white border-b border-stone-200 h-12 flex items-center px-5 gap-4">
        <div className="size-6 rounded-md bg-[#B5622A] flex items-center justify-center shrink-0">
          <Bot className="size-3.5 text-white" />
        </div>
        <span className="text-sm font-semibold text-stone-800 tracking-tight">Nexus</span>
      </div>

      <div className="max-w-3xl mx-auto px-5 py-6">
        <Link
          to="/"
          className="inline-flex items-center gap-1.5 text-sm text-stone-400 hover:text-stone-700 transition-colors mb-5"
        >
          <ArrowLeft className="size-3.5" />
          Back to overview
        </Link>

        {/* Task header */}
        <div className="flex items-start gap-3 mb-6">
          <Bot className="size-5 text-stone-300 mt-0.5 shrink-0" />
          <div>
            <h1 className="text-base font-semibold text-stone-900">{task.title}</h1>
            <div className="flex items-center gap-3 mt-1 text-xs text-stone-400 flex-wrap">
              <code className="font-mono">#{task.id}</code>
              <span>{task.agentType} · {task.agentName}</span>
              {task.metadata?.repository && (
                <span className="flex items-center gap-1">
                  <GitBranch className="size-3" />
                  {task.metadata.repository}
                  {task.metadata.branch && (
                    <><span className="opacity-40">·</span>
                    <span className="font-mono">{task.metadata.branch}</span></>
                  )}
                </span>
              )}
            </div>
            {task.error && (
              <p className="mt-2.5 text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
                {task.error}
              </p>
            )}
          </div>
        </div>

        {/* Log panel */}
        <div className="bg-white rounded-xl border border-stone-200 shadow-sm overflow-hidden">
          <div className="px-4 py-2.5 border-b border-stone-100 bg-stone-50">
            <span className="text-xs font-semibold text-stone-400 uppercase tracking-wide">Logs</span>
          </div>
          <div className="p-4 font-mono text-xs space-y-1.5">
            {task.logs.length === 0 ? (
              <p className="text-stone-300">No logs available.</p>
            ) : (
              task.logs.map((entry, i) => (
                <div key={i} className="flex gap-4">
                  <span className="text-stone-300 shrink-0 w-20">
                    {new Date(entry.timestamp).toLocaleTimeString()}
                  </span>
                  <span className={cn(LEVEL_STYLES[entry.level] ?? 'text-stone-500')}>
                    {entry.message}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
