import { useEffect, useRef, useState, type FormEvent } from "react";
import { ChevronsUpDown, SendHorizontal } from "lucide-react";
import type {
  WorkspaceAgentOption,
  WorkspaceConsultMessageView,
  WorkspaceTaskView,
} from "../utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Select } from "@/components/ui/select";
import { cn } from "@/lib/utils";
import { STATUS_META, timeAgo } from "../utils";

type WorkspaceTrackingPanelProps = {
  agents: WorkspaceAgentOption[];
  tasksForAgent: WorkspaceTaskView[];
  messages: WorkspaceConsultMessageView[];
  selectedAgentId: string;
  selectedTaskId: string;
  selectedTask?: WorkspaceTaskView;
  input: string;
  isLoadingAgents: boolean;
  isSending: boolean;
  onSelectedAgentChange: (agentId: string) => void;
  onSelectedTaskChange: (taskId: string) => void;
  onInputChange: (next: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
};

function messageRoleLabel(role: WorkspaceConsultMessageView["role"]): string {
  return role === "user" ? "You" : "Agent";
}

function detailValue(value: string | null | undefined): string {
  return value || "-";
}

export function WorkspaceTrackingPanel({
  agents,
  tasksForAgent,
  messages,
  selectedAgentId,
  selectedTaskId,
  selectedTask,
  input,
  isLoadingAgents,
  isSending,
  onSelectedAgentChange,
  onSelectedTaskChange,
  onInputChange,
  onSubmit,
}: WorkspaceTrackingPanelProps) {
  const [isTaskPickerOpen, setIsTaskPickerOpen] = useState(false);
  const bottomAnchorRef = useRef<HTMLDivElement | null>(null);

  const hasAgents = agents.length > 0;
  const hasTasks = tasksForAgent.length > 0;
  const canSubmit =
    Boolean(selectedTask) && input.trim().length > 0 && !isSending;

  // Auto-scroll to latest message (or the waiting bubble when isSending)
  useEffect(() => {
    if (messages.length === 0 && !isSending) return;
    const id = window.requestAnimationFrame(() => {
      bottomAnchorRef.current?.scrollIntoView({
        behavior: "smooth",
        block: "end",
      });
    });
    return () => window.cancelAnimationFrame(id);
  }, [messages.length, selectedTaskId, isSending]);

  return (
    // Use a plain flex-col div styled like a card — avoids CardHeader's built-in grid
    <div className="flex h-full min-h-0 flex-col overflow-hidden rounded-xl border bg-card text-card-foreground shadow-sm">
      {/* ── Top section: Agent+Task picker (left) | Selected task detail (right) ── */}
      <div className="shrink-0 border-b px-6 py-5">
        <div className="grid grid-cols-2 gap-6 items-start">
          {/* Left column: selectors */}
          <div className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <label htmlFor="tracking-agent" className="text-sm font-medium">
                Agent
              </label>
              <Select
                id="tracking-agent"
                value={selectedAgentId}
                onChange={(e) => onSelectedAgentChange(e.target.value)}
                disabled={!hasAgents || isSending}
              >
                {isLoadingAgents && <option value="">Loading agent instances…</option>}
                {agents.map((agent) => (
                  <option key={agent.id} value={agent.id} selected={agent.id === selectedAgentId}>
                    {agent.label} — {agent.subtitle}
                  </option>
                ))}
              </Select>
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-sm font-medium">Task</label>
              <Dialog
                open={isTaskPickerOpen}
                onOpenChange={setIsTaskPickerOpen}
              >
                <DialogTrigger asChild>
                  <Button
                    type="button"
                    variant="outline"
                    className="w-full justify-between gap-3 px-3 font-normal"
                    disabled={!hasTasks || isSending}
                  >
                    <span className="truncate text-left">
                      {selectedTask
                        ? selectedTask.question
                        : selectedAgentId
                        ? "Choose a task…"
                        : "Select an agent first"}
                    </span>
                    <ChevronsUpDown className="size-4 shrink-0 text-muted-foreground" />
                  </Button>
                </DialogTrigger>

                <DialogContent className="max-w-lg">
                  <DialogHeader>
                    <DialogTitle>Select a task</DialogTitle>
                    <DialogDescription>
                      Choose the task you want to consult about for this agent.
                    </DialogDescription>
                  </DialogHeader>
                  <ScrollArea className="max-h-[420px] -mx-1">
                    <div className="flex flex-col gap-1 px-1">
                      {tasksForAgent.map((task) => {
                        const isSelected = task.id === selectedTaskId;
                        return (
                          <button
                            key={task.id}
                            type="button"
                            onClick={() => {
                              onSelectedTaskChange(task.id);
                              setIsTaskPickerOpen(false);
                            }}
                            className={cn(
                              "w-full rounded-lg border px-4 py-3 text-left transition-colors",
                              isSelected
                                ? "border-primary bg-primary/5"
                                : "border-transparent hover:border-border hover:bg-muted/40"
                            )}
                          >
                            <div className="flex items-start justify-between gap-3">
                              <p className="line-clamp-2 text-sm font-medium leading-snug">
                                {task.question}
                              </p>
                              <Badge
                                variant={STATUS_META[task.status].badgeVariant}
                                className="shrink-0 mt-0.5"
                              >
                                {STATUS_META[task.status].label}
                              </Badge>
                            </div>
                            <div className="mt-1.5 flex items-center gap-2 text-xs text-muted-foreground">
                              <span className="truncate">{detailValue(task.repo)}</span>
                              <span className="shrink-0">·</span>
                              <span className="shrink-0">{task.agentLabel}</span>
                              <span className="shrink-0 ml-auto">{timeAgo(task.updatedAt)}</span>
                            </div>
                          </button>
                        );
                      })}
                    </div>
                  </ScrollArea>
                </DialogContent>
              </Dialog>

              <p className="text-xs text-muted-foreground">
                {hasTasks
                  ? `${tasksForAgent.length} task${
                      tasksForAgent.length === 1 ? "" : "s"
                    } available`
                  : "No tasks available for the selected agent."}
              </p>
            </div>
          </div>

          {/* Right column: selected task detail */}
          <div className="rounded-xl bg-muted/40 p-4">
            <div className="flex items-start justify-between gap-3">
              <p className="text-xs font-medium uppercase tracking-widest text-muted-foreground">
                Selected task
              </p>
              {selectedTask ? (
                <Badge variant={STATUS_META[selectedTask.status].badgeVariant}>
                  {STATUS_META[selectedTask.status].label}
                </Badge>
              ) : null}
            </div>

            <CardTitle
              className="mt-2 line-clamp-2 text-sm font-semibold leading-snug"
              title={selectedTask?.question}
            >
              {selectedTask?.question ?? (
                <span className="font-normal text-muted-foreground">
                  No task selected
                </span>
              )}
            </CardTitle>

            <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3">
              {(
                [
                  ["Agent", selectedTask?.agentLabel],
                  ["Repository", selectedTask?.repo],
                  ["Project", selectedTask?.project],
                  [
                    "Updated",
                    selectedTask ? timeAgo(selectedTask.updatedAt) : null,
                  ],
                ] as [string, string | null | undefined][]
              ).map(([label, value]) => (
                <div key={label}>
                  <dt className="text-xs text-muted-foreground">{label}</dt>
                  <dd className="mt-0.5 truncate text-sm" title={value ?? "-"}>
                    {detailValue(value)}
                  </dd>
                </div>
              ))}
            </dl>

            {selectedTask?.error ? (
              <div className="mt-4 rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                {selectedTask.error}
              </div>
            ) : null}
          </div>
        </div>

      </div>

      {/* ── Bottom section: chat ── */}
      <div className="flex min-h-0 flex-1 flex-col gap-4 px-6 py-5">
        {/* Chat label */}
        <div className="shrink-0">
          <p className="text-xs font-medium uppercase tracking-widest text-muted-foreground">
            Chat
          </p>
          <p className="mt-1 text-sm text-muted-foreground">
            {selectedTask
              ? "Ask for the latest process, blockers, or ETA."
              : "Select an agent and task to start chatting."}
          </p>
        </div>

        {/* Scrollable messages — fills remaining vertical space */}
        <div className="min-h-0 flex-1">
          <ScrollArea className="h-full">
            <div className="flex flex-col gap-2 pb-2 pr-1">
              {messages.map((message) => (
                <article
                  key={message.id}
                  className={cn(
                    "max-w-[88%] rounded-lg px-3 py-2 text-sm",
                    "transition-all duration-300 ease-out",
                    "motion-safe:animate-in motion-safe:fade-in-0 motion-safe:slide-in-from-bottom-2",
                    message.role === "user"
                      ? "ml-auto bg-primary text-primary-foreground"
                      : "bg-muted"
                  )}
                >
                  <p className="text-xs font-semibold opacity-70">
                    {messageRoleLabel(message.role)}
                  </p>
                  <p className="mt-1 break-words leading-relaxed">
                    {message.text}
                  </p>
                  <p className="mt-1 text-[11px] opacity-60">
                    {timeAgo(message.time)}
                  </p>
                </article>
              ))}

              {/* Waiting animation — shown while agent is responding */}
              {isSending && (
                <article
                  className={cn(
                    "max-w-[88%] rounded-lg px-3 py-2 text-sm bg-muted",
                    "motion-safe:animate-in motion-safe:fade-in-0 motion-safe:slide-in-from-bottom-2",
                    "transition-all duration-300 ease-out"
                  )}
                  aria-label="Agent is typing"
                >
                  <p className="text-xs font-semibold opacity-70">Agent</p>
                  <div className="mt-2 mb-1 flex items-center gap-1.5">
                    <span
                      className="size-2 rounded-full bg-current opacity-60 animate-bounce"
                      style={{ animationDelay: "0ms", animationDuration: "1s" }}
                    />
                    <span
                      className="size-2 rounded-full bg-current opacity-60 animate-bounce"
                      style={{ animationDelay: "160ms", animationDuration: "1s" }}
                    />
                    <span
                      className="size-2 rounded-full bg-current opacity-60 animate-bounce"
                      style={{ animationDelay: "320ms", animationDuration: "1s" }}
                    />
                  </div>
                </article>
              )}

              <div ref={bottomAnchorRef} />
            </div>
          </ScrollArea>
        </div>

        {/* Input bar — pinned to bottom */}
        <form onSubmit={onSubmit} className="shrink-0 flex flex-col gap-2">
          <div className="flex items-center gap-2">
            <Input
              value={input}
              onChange={(e) => onInputChange(e.target.value)}
              placeholder={
                selectedTask
                  ? "Ask for the latest process, blockers, or ETA…"
                  : "Select a task first."
              }
              disabled={!selectedTask || isSending}
            />
            <Button
              type="submit"
              size="icon"
              aria-label="Consult selected task"
              disabled={!canSubmit}
            >
              <SendHorizontal />
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
