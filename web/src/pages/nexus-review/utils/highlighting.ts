import { type CSSProperties, useEffect, useMemo, useState } from 'react';
import { codeToTokens, type BundledLanguage } from 'shiki';
import type { ParsedDiffFile } from '@/lib/reviewDiff';
import { SHIKI_THEME } from './constants';
import type { ShikiToken } from './types';
const EMPTY_HIGHLIGHT_TOKENS: Record<string, ShikiToken[][]> = {};

export function inferHighlightLanguage(filePath: string): BundledLanguage | null {
  const normalized = filePath.toLowerCase();

  if (
    normalized.endsWith('docker-compose.yml') ||
    normalized.endsWith('docker-compose.yaml') ||
    normalized.endsWith('compose.yml') ||
    normalized.endsWith('compose.yaml')
  ) {
    return 'yaml';
  }
  if (normalized.endsWith('dockerfile') || normalized.includes('/dockerfile')) {
    return 'dockerfile';
  }
  if (
    normalized.endsWith('/nginx') ||
    normalized.endsWith('nginx.conf') ||
    normalized.endsWith('.nginx.conf')
  ) {
    return 'nginx';
  }
  if (normalized.endsWith('.tsx')) {
    return 'tsx';
  }
  if (normalized.endsWith('.ts')) {
    return 'typescript';
  }
  if (normalized.endsWith('.jsx')) {
    return 'jsx';
  }
  if (normalized.endsWith('.js')) {
    return 'javascript';
  }
  if (normalized.endsWith('.py')) {
    return 'python';
  }
  if (normalized.endsWith('.java')) {
    return 'java';
  }
  if (normalized.endsWith('.go')) {
    return 'go';
  }
  if (
    normalized.endsWith('.cpp') ||
    normalized.endsWith('.cc') ||
    normalized.endsWith('.cxx') ||
    normalized.endsWith('.hpp') ||
    normalized.endsWith('.hh') ||
    normalized.endsWith('.hxx')
  ) {
    return 'cpp';
  }
  if (normalized.endsWith('.c') || normalized.endsWith('.h')) {
    return 'c';
  }
  if (normalized.endsWith('.sh') || normalized.endsWith('.bash') || normalized.endsWith('.zsh')) {
    return 'bash';
  }
  if (normalized.endsWith('.yml') || normalized.endsWith('.yaml')) {
    return 'yaml';
  }

  return null;
}

async function highlightCodeWithShiki(code: string, language: BundledLanguage): Promise<ShikiToken[][]> {
  try {
    const result = await codeToTokens(code, {
      lang: language,
      theme: SHIKI_THEME,
    });
    return result.tokens;
  } catch {
    return [];
  }
}

export function shikiTokenStyle(token: ShikiToken): CSSProperties {
  const style: CSSProperties = {};
  if (token.color) {
    style.color = token.color;
  }
  if (typeof token.fontStyle === 'number') {
    if (token.fontStyle & 1) {
      style.fontStyle = 'italic';
    }
    if (token.fontStyle & 2) {
      style.fontWeight = 600;
    }
    if (token.fontStyle & 4) {
      style.textDecoration = 'underline';
    }
  }
  return style;
}

export function useHighlightedHunkTokens(activeFile: ParsedDiffFile | null): Record<string, ShikiToken[][]> {
  const [tokensByHunkId, setTokensByHunkId] = useState<Record<string, ShikiToken[][]>>({});
  const language = useMemo(
    () => (activeFile ? inferHighlightLanguage(activeFile.displayPath) : null),
    [activeFile],
  );
  const canHighlight = Boolean(activeFile && language && activeFile.hunks.length > 0);

  useEffect(() => {
    let cancelled = false;

    if (!activeFile || !language || activeFile.hunks.length === 0) {
      return () => {
        cancelled = true;
      };
    }

    void Promise.all(
      activeFile.hunks.map(async hunk => {
        const code = hunk.lines.map(line => line.text || ' ').join('\n');
        const tokens = await highlightCodeWithShiki(code, language);
        return [hunk.id, tokens] as const;
      }),
    ).then(results => {
      if (cancelled) {
        return;
      }
      setTokensByHunkId(Object.fromEntries(results));
    });

    return () => {
      cancelled = true;
    };
  }, [activeFile, language]);

  return canHighlight ? tokensByHunkId : EMPTY_HIGHLIGHT_TOKENS;
}
