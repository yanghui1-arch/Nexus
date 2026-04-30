import type { ParsedDiffFile } from '@/lib/reviewDiff';
import type {
  FileTreeDirectoryNode,
  FileTreeLeafNode,
  FileTreeNode,
  MutableFileTreeDirectoryNode,
} from './types';

export function normalizeFileMatch(file: ParsedDiffFile, candidate: string): boolean {
  return file.displayPath === candidate ||
    file.newPath === candidate ||
    file.oldPath === candidate;
}

function sortFileTreeNodes(nodes: FileTreeNode[]): FileTreeNode[] {
  return [...nodes].sort((left, right) => {
    if (left.type !== right.type) {
      return left.type === 'directory' ? -1 : 1;
    }
    return left.name.localeCompare(right.name);
  });
}

export function buildFileTree(files: ParsedDiffFile[]): FileTreeNode[] {
  const root: MutableFileTreeDirectoryNode = {
    key: '',
    name: '',
    directories: new Map<string, MutableFileTreeDirectoryNode>(),
    files: [],
  };

  for (const file of files) {
    const parts = file.displayPath.split('/');
    let current = root;
    let currentKey = '';

    for (const part of parts.slice(0, -1)) {
      currentKey = currentKey ? `${currentKey}/${part}` : part;
      const existing = current.directories.get(part);
      if (existing) {
        current = existing;
        continue;
      }

      const nextDirectory: MutableFileTreeDirectoryNode = {
        key: currentKey,
        name: part,
        directories: new Map<string, MutableFileTreeDirectoryNode>(),
        files: [],
      };
      current.directories.set(part, nextDirectory);
      current = nextDirectory;
    }

    const fileName = parts[parts.length - 1] ?? file.displayPath;
    const leaf: FileTreeLeafNode = {
      type: 'file',
      key: file.displayPath,
      name: fileName,
      file,
    };
    current.files.push(leaf);
  }

  const materialize = (directory: MutableFileTreeDirectoryNode): FileTreeNode[] => {
    const childDirectories: FileTreeDirectoryNode[] = [...directory.directories.values()].map(child => ({
      type: 'directory',
      key: child.key,
      name: child.name,
      children: materialize(child),
    }));

    return sortFileTreeNodes([
      ...childDirectories,
      ...directory.files.sort((left, right) => left.name.localeCompare(right.name)),
    ]);
  };

  return materialize(root);
}

export function collectDirectoryKeys(nodes: FileTreeNode[]): string[] {
  const keys: string[] = [];
  for (const node of nodes) {
    if (node.type !== 'directory') {
      continue;
    }
    keys.push(node.key);
    keys.push(...collectDirectoryKeys(node.children));
  }
  return keys;
}

export function directoryAncestors(filePath: string): string[] {
  const parts = filePath.split('/');
  const ancestors: string[] = [];
  for (let index = 1; index < parts.length; index += 1) {
    ancestors.push(parts.slice(0, index).join('/'));
  }
  return ancestors;
}
