import {
  ChevronDown,
  ChevronRight,
  FileCode2,
  Folder,
  FolderOpen,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import type { FileTreeNode } from '../utils/types';

type ChangedFilesTreeProps = {
  nodes: FileTreeNode[];
  depth?: number;
  activeFilePath: string;
  expandedDirectories: Record<string, boolean>;
  onToggleDirectory: (directoryKey: string) => void;
  onSelectFile: (filePath: string) => void;
};

export function ChangedFilesTree({
  nodes,
  depth = 0,
  activeFilePath,
  expandedDirectories,
  onToggleDirectory,
  onSelectFile,
}: ChangedFilesTreeProps) {
  return (
    <div className="space-y-1">
      {nodes.map(node => {
        const basePadding = 14 + depth * 16;

        if (node.type === 'directory') {
          const isExpanded = expandedDirectories[node.key] !== false;
          return (
            <div key={node.key} className="space-y-1">
              <button
                type="button"
                onClick={() => onToggleDirectory(node.key)}
                className="flex w-full items-center gap-2 rounded-md py-1.5 pr-2 text-left text-sm text-foreground/80 transition-colors hover:bg-background/70 hover:text-foreground"
                style={{ paddingLeft: basePadding }}
              >
                {isExpanded ? (
                  <ChevronDown className="size-4 shrink-0 text-muted-foreground" />
                ) : (
                  <ChevronRight className="size-4 shrink-0 text-muted-foreground" />
                )}
                {isExpanded ? (
                  <FolderOpen className="size-4 shrink-0 text-amber-600" />
                ) : (
                  <Folder className="size-4 shrink-0 text-amber-600" />
                )}
                <span className="truncate">{node.name}</span>
              </button>
              {isExpanded ? (
                <ChangedFilesTree
                  nodes={node.children}
                  depth={depth + 1}
                  activeFilePath={activeFilePath}
                  expandedDirectories={expandedDirectories}
                  onToggleDirectory={onToggleDirectory}
                  onSelectFile={onSelectFile}
                />
              ) : null}
            </div>
          );
        }

        const isActive = node.file.displayPath === activeFilePath;
        return (
          <button
            key={node.key}
            type="button"
            onClick={() => onSelectFile(node.file.displayPath)}
            className={cn(
              'flex w-full items-center justify-between gap-2 rounded-md py-1.5 pr-2 text-left transition-colors',
              isActive
                ? 'bg-background text-foreground shadow-sm ring-1 ring-border'
                : 'text-muted-foreground hover:bg-background/70 hover:text-foreground',
            )}
            style={{ paddingLeft: basePadding + 20 }}
            title={node.file.displayPath}
          >
            <span className="flex min-w-0 items-center gap-2">
              <FileCode2 className="size-4 shrink-0" />
              <span className="truncate font-mono text-[12px]">{node.name}</span>
            </span>
            <span className="shrink-0 font-mono text-[11px]">
              <span className="text-emerald-600">+{node.file.additions}</span>
              <span className="ml-1 text-red-600">-{node.file.deletions}</span>
            </span>
          </button>
        );
      })}
    </div>
  );
}
