import { useState, useMemo } from 'react';
import { 
  GitBranch, 
  Play, 
  CheckCircle, 
  XCircle, 
  AlertCircle, 
  Clock,
  ChevronRight,
  Terminal,
  Calendar,
  GitCommit,
  Settings,
  Code,
  Circle,
  Loader2
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { ScrollArea } from '@/components/ui/scroll-area';
import { mockWorkflows } from '@/data/mockWorkflows';
import type { AgentWorkflow, Stage, StageStatus } from '@/types/agent';

const stageIcons: Record<string, React.ReactNode> = {
  init: <Settings className="h-5 w-5" />,
  github: <GitBranch className="h-5 w-5" />,
  work: <Code className="h-5 w-5" />,
  git: <GitCommit className="h-5 w-5" />,
  finish: <CheckCircle className="h-5 w-5" />,
};

const statusConfig: Record<StageStatus, { 
  icon: React.ReactNode; 
  color: string; 
  bgColor: string;
  borderColor: string;
  label: string;
}> = {
  pending: {
    icon: <Circle className="h-4 w-4" />,
    color: 'text-slate-400',
    bgColor: 'bg-slate-50',
    borderColor: 'border-slate-200',
    label: 'Pending',
  },
  running: {
    icon: <Loader2 className="h-4 w-4 animate-spin" />,
    color: 'text-blue-500',
    bgColor: 'bg-blue-50',
    borderColor: 'border-blue-200',
    label: 'Running',
  },
  completed: {
    icon: <CheckCircle className="h-4 w-4" />,
    color: 'text-emerald-500',
    bgColor: 'bg-emerald-50',
    borderColor: 'border-emerald-200',
    label: 'Completed',
  },
  failed: {
    icon: <XCircle className="h-4 w-4" />,
    color: 'text-red-500',
    bgColor: 'bg-red-50',
    borderColor: 'border-red-200',
    label: 'Failed',
  },
  error: {
    icon: <AlertCircle className="h-4 w-4" />,
    color: 'text-amber-500',
    bgColor: 'bg-amber-50',
    borderColor: 'border-amber-200',
    label: 'Error',
  },
};

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  const remaining = seconds % 60;
  return remaining > 0 ? `${minutes}m ${remaining}s` : `${minutes}m`;
}

function formatTime(isoString: string): string {
  return new Date(isoString).toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

function StageBlock({ 
  stage, 
  isLast, 
  onClick 
}: { 
  stage: Stage; 
  isLast: boolean;
  onClick: () => void;
}) {
  const config = statusConfig[stage.status];
  const isClickable = stage.status !== 'pending' && stage.logs.length > 0;
  
  return (
    <div className="relative flex flex-col items-center">
      {/* Stage Block */}
      <button
        onClick={onClick}
        disabled={!isClickable}
        className={cn(
          "relative flex flex-col items-center gap-2 p-4 rounded-xl border-2 transition-all duration-300",
          "min-w-[140px] max-w-[180px]",
          config.bgColor,
          config.borderColor,
          isClickable && "hover:shadow-md hover:scale-105 cursor-pointer",
          !isClickable && "cursor-default opacity-70"
        )}
      >
        {/* Icon */}
        <div className={cn("flex items-center justify-center w-10 h-10 rounded-full bg-white shadow-sm", config.color)}>
          {stageIcons[stage.id] || <Play className="h-5 w-5" />}
        </div>
        
        {/* Stage Name */}
        <span className="font-medium text-sm text-slate-700 text-center leading-tight">
          {stage.name}
        </span>
        
        {/* Status Badge */}
        <Badge 
          variant="outline" 
          className={cn(
            "text-xs font-medium border-current",
            config.color,
            stage.status === 'running' && "animate-pulse"
          )}
        >
          {config.label}
        </Badge>
        
        {/* Duration */}
        {stage.duration && (
          <div className="flex items-center gap-1 text-xs text-slate-500">
            <Clock className="h-3 w-3" />
            {formatDuration(stage.duration)}
          </div>
        )}
        
        {/* Running Indicator - Circle Animation */}
        {stage.status === 'running' && (
          <div className="absolute -top-2 -right-2">
            <span className="relative flex h-4 w-4">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-4 w-4 bg-blue-500"></span>
            </span>
          </div>
        )}
      </button>
      
      {/* Connector Line */}
      {!isLast && (
        <div className="hidden md:flex items-center absolute left-full top-1/2 -translate-y-1/2 w-8">
          <div className={cn(
            "h-0.5 flex-1 transition-all duration-500",
            stage.status === 'completed' ? "bg-emerald-400" : "bg-slate-200"
          )} />
          <ChevronRight className={cn(
            "h-4 w-4 -ml-1",
            stage.status === 'completed' ? "text-emerald-400" : "text-slate-300"
          )} />
        </div>
      )}
    </div>
  );
}

function WorkflowCard({ 
  workflow, 
  onStageClick 
}: { 
  workflow: AgentWorkflow;
  onStageClick: (stage: Stage) => void;
}) {
  const overallConfig = statusConfig[workflow.status];
  
  return (
    <Card className="w-full overflow-hidden border-slate-200">
      <CardHeader className="pb-4">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div className="flex items-start gap-3">
            <div className={cn("p-2 rounded-lg", overallConfig.bgColor)}>
              {overallConfig.icon}
            </div>
            <div>
              <CardTitle className="text-lg font-semibold text-slate-800">
                {workflow.name}
              </CardTitle>
              <CardDescription className="flex items-center gap-2 mt-1 flex-wrap">
                <span className="flex items-center gap-1">
                  <GitBranch className="h-3.5 w-3.5" />
                  {workflow.branch}
                </span>
                <span className="text-slate-300">|</span>
                <span className="flex items-center gap-1">
                  <GitBranch className="h-3.5 w-3.5" />
                  {workflow.repository}
                </span>
              </CardDescription>
            </div>
          </div>
          
          <div className="flex items-center gap-4 text-sm text-slate-500">
            <div className="flex items-center gap-1.5">
              <Calendar className="h-4 w-4" />
              {new Date(workflow.startTime).toLocaleDateString('en-US', {
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit',
              })}
            </div>
            <Badge className={cn(overallConfig.color, overallConfig.bgColor, overallConfig.borderColor)}>
              {overallConfig.label}
            </Badge>
          </div>
        </div>
      </CardHeader>
      
      <CardContent className="pt-0">
        {/* Stage Pipeline - Horizontal on desktop, vertical on mobile */}
        <div className="flex flex-col md:flex-row md:items-center gap-6 md:gap-4 overflow-x-auto pb-4">
          {workflow.stages.map((stage, index) => (
            <StageBlock
              key={stage.id}
              stage={stage}
              isLast={index === workflow.stages.length - 1}
              onClick={() => onStageClick(stage)}
            />
          ))}
        </div>
        
        {/* Error Message */}
        {workflow.stages.some(s => s.error) && (
          <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg">
            <div className="flex items-center gap-2 text-red-700">
              <AlertCircle className="h-4 w-4" />
              <span className="font-medium text-sm">
                {workflow.stages.find(s => s.error)?.error}
              </span>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function StageDetailsDialog({ 
  stage, 
  open, 
  onOpenChange 
}: { 
  stage: Stage | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  if (!stage) return null;
  
  const config = statusConfig[stage.status];
  
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[80vh] flex flex-col">
        <DialogHeader>
          <div className="flex items-center gap-3">
            <div className={cn("p-2 rounded-lg", config.bgColor)}>
              {stageIcons[stage.id] || <Terminal className="h-5 w-5" />}
            </div>
            <div>
              <DialogTitle className="text-xl">{stage.name}</DialogTitle>
              <DialogDescription className="flex items-center gap-2 mt-1">
                <Badge variant="outline" className={cn(config.color)}>
                  {config.label}
                </Badge>
                {stage.duration && (
                  <span className="text-slate-500">
                    Duration: {formatDuration(stage.duration)}
                  </span>
                )}
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>
        
        <div className="mt-4 space-y-4">
          {/* Timeline Info */}
          <div className="grid grid-cols-2 gap-4 p-4 bg-slate-50 rounded-lg">
            {stage.startTime && (
              <div>
                <p className="text-sm text-slate-500">Started</p>
                <p className="font-medium text-slate-700">{formatTime(stage.startTime)}</p>
              </div>
            )}
            {stage.endTime && (
              <div>
                <p className="text-sm text-slate-500">Ended</p>
                <p className="font-medium text-slate-700">{formatTime(stage.endTime)}</p>
              </div>
            )}
          </div>
          
          {/* Error Display */}
          {stage.error && (
            <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
              <div className="flex items-center gap-2 text-red-700 mb-2">
                <AlertCircle className="h-4 w-4" />
                <span className="font-medium">Error</span>
              </div>
              <p className="text-red-600 text-sm font-mono">{stage.error}</p>
            </div>
          )}
          
          {/* Logs */}
          <div>
            <h4 className="text-sm font-medium text-slate-700 mb-2 flex items-center gap-2">
              <Terminal className="h-4 w-4" />
              Execution Logs
            </h4>
            <ScrollArea className="h-[300px] w-full rounded-md border bg-slate-950 p-4">
              <div className="space-y-2">
                {stage.logs.map((log, index) => (
                  <div key={index} className="flex gap-3 text-sm font-mono">
                    <span className="text-slate-500 shrink-0">
                      {formatTime(log.timestamp)}
                    </span>
                    <span className={cn(
                      "shrink-0 w-16 text-right",
                      log.level === 'error' && "text-red-400",
                      log.level === 'warning' && "text-amber-400",
                      log.level === 'success' && "text-emerald-400",
                      log.level === 'info' && "text-blue-400",
                    )}>
                      [{log.level.toUpperCase()}]
                    </span>
                    <span className="text-slate-300">{log.message}</span>
                  </div>
                ))}
              </div>
            </ScrollArea>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

export default function LogPage() {
  const [selectedStage, setSelectedStage] = useState<Stage | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  
  const workflows = useMemo(() => mockWorkflows, []);
  
  const handleStageClick = (stage: Stage) => {
    setSelectedStage(stage);
    setDialogOpen(true);
  };
  
  // Summary statistics
  const stats = useMemo(() => {
    const running = workflows.filter(w => w.status === 'running').length;
    const completed = workflows.filter(w => w.status === 'completed').length;
    const failed = workflows.filter(w => w.status === 'failed' || w.status === 'error').length;
    return { running, completed, failed };
  }, [workflows]);
  
  return (
    <div className="min-h-screen bg-slate-50">
      {/* Header */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-10">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div>
              <h1 className="text-2xl font-bold text-slate-800">Agent Workflows</h1>
              <p className="text-slate-500 text-sm mt-1">
                Monitor and track agent execution pipelines
              </p>
            </div>
            
            {/* Stats */}
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2 px-4 py-2 bg-blue-50 rounded-lg">
                <Loader2 className="h-4 w-4 text-blue-500 animate-spin" />
                <span className="text-sm font-medium text-blue-700">{stats.running} Running</span>
              </div>
              <div className="flex items-center gap-2 px-4 py-2 bg-emerald-50 rounded-lg">
                <CheckCircle className="h-4 w-4 text-emerald-500" />
                <span className="text-sm font-medium text-emerald-700">{stats.completed} Completed</span>
              </div>
              <div className="flex items-center gap-2 px-4 py-2 bg-red-50 rounded-lg">
                <XCircle className="h-4 w-4 text-red-500" />
                <span className="text-sm font-medium text-red-700">{stats.failed} Failed</span>
              </div>
            </div>
          </div>
        </div>
      </header>
      
      {/* Main Content */}
      <main className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="space-y-6">
          {workflows.map((workflow) => (
            <WorkflowCard
              key={workflow.id}
              workflow={workflow}
              onStageClick={handleStageClick}
            />
          ))}
        </div>
      </main>
      
      {/* Stage Details Dialog */}
      <StageDetailsDialog
        stage={selectedStage}
        open={dialogOpen}
        onOpenChange={setDialogOpen}
      />
    </div>
  );
}
