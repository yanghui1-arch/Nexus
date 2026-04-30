import Markdown from 'markdown-to-jsx';
import {
  Fragment,
  type CSSProperties,
  type ComponentPropsWithoutRef,
  useEffect,
  useMemo,
  useState,
} from 'react';
import { codeToTokens, type BundledLanguage } from 'shiki';
import { cn } from '@/lib/utils';

const GITHUB_MARKDOWN_SANS_FAMILY =
  '-apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans", Helvetica, Arial, sans-serif, "Apple Color Emoji", "Segoe UI Emoji"';

const GITHUB_MARKDOWN_MONO_FAMILY =
  'ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace';

const MARKDOWN_SHIKI_THEME = 'github-light';

const MARKDOWN_LANGUAGE_ALIASES: Record<string, BundledLanguage> = {
  bash: 'bash',
  c: 'c',
  'c++': 'cpp',
  cc: 'cpp',
  cpp: 'cpp',
  cxx: 'cpp',
  java: 'java',
  javascript: 'javascript',
  js: 'javascript',
  py: 'python',
  python: 'python',
  sh: 'bash',
  shell: 'bash',
  shellscript: 'bash',
  ts: 'typescript',
  tsx: 'tsx',
  typescript: 'typescript',
  zsh: 'bash',
};

type MarkdownShikiToken = {
  color?: string;
  content: string;
  fontStyle?: number;
};

const GITHUB_MARKDOWN_HEADING_STYLE: CSSProperties = {
  fontFamily: GITHUB_MARKDOWN_SANS_FAMILY,
};

const GITHUB_MARKDOWN_ROOT_STYLE: CSSProperties = {
  fontFamily: GITHUB_MARKDOWN_SANS_FAMILY,
};

type MarkdownContentProps = {
  content: string;
  className?: string;
  emptyState?: string | null;
};

const markdownHighlightCache = new Map<string, Promise<MarkdownShikiToken[][]>>();

function markdownShikiTokenStyle(token: MarkdownShikiToken): CSSProperties {
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

function flattenMarkdownCodeChildren(children: ComponentPropsWithoutRef<'code'>['children']): string {
  if (typeof children === 'string') {
    return children;
  }
  if (Array.isArray(children)) {
    return children.map(child => (typeof child === 'string' ? child : '')).join('');
  }
  return '';
}

function normalizeMarkdownLanguage(className?: string): BundledLanguage | null {
  if (!className) {
    return null;
  }

  const match = className.match(/(?:^|\s)(?:lang|language)-([^\s]+)/i);
  if (!match) {
    return null;
  }

  return MARKDOWN_LANGUAGE_ALIASES[match[1].toLowerCase()] ?? null;
}

async function highlightMarkdownCode(
  code: string,
  language: BundledLanguage,
): Promise<MarkdownShikiToken[][]> {
  const cacheKey = `${language}\u0000${code}`;
  const cached = markdownHighlightCache.get(cacheKey);
  if (cached) {
    return cached;
  }

  const nextResult = codeToTokens(code, {
    lang: language,
    theme: MARKDOWN_SHIKI_THEME,
  })
    .then(result => result.tokens as MarkdownShikiToken[][])
    .catch(() => []);

  markdownHighlightCache.set(cacheKey, nextResult);
  return nextResult;
}

function MarkdownLink({
  className,
  href,
  children,
  ...props
}: ComponentPropsWithoutRef<'a'>) {
  const isExternal = typeof href === 'string' && /^https?:\/\//.test(href);

  return (
    <a
      {...props}
      href={href}
      target={isExternal ? '_blank' : props.target}
      rel={isExternal ? 'noreferrer' : props.rel}
      className={cn(
        'inline-flex items-center gap-1 text-foreground underline underline-offset-4',
        className,
      )}
    >
      {children}
    </a>
  );
}

function MarkdownCode({
  className,
  children,
  style,
  ...props
}: ComponentPropsWithoutRef<'code'>) {
  const codeText = useMemo(() => flattenMarkdownCodeChildren(children), [children]);
  const isFencedCodeBlock = typeof className === 'string' &&
    /(?:^|\s)(?:lang|language)-[^\s]+/i.test(className);
  const highlightLanguage = useMemo(
    () => normalizeMarkdownLanguage(className),
    [className],
  );
  const isBlockCode = isFencedCodeBlock;
  const [highlightedTokens, setHighlightedTokens] = useState<MarkdownShikiToken[][] | null>(null);

  useEffect(() => {
    let cancelled = false;

    if (!highlightLanguage || !codeText) {
      setHighlightedTokens(null);
      return () => {
        cancelled = true;
      };
    }

    setHighlightedTokens(null);
    void highlightMarkdownCode(codeText, highlightLanguage).then(tokens => {
      if (!cancelled) {
        setHighlightedTokens(tokens);
      }
    });

    return () => {
      cancelled = true;
    };
  }, [codeText, highlightLanguage]);

  return (
    <code
      {...props}
      style={{
        fontFamily: GITHUB_MARKDOWN_MONO_FAMILY,
        ...style,
      }}
      className={cn(
        isBlockCode
          ? 'font-mono text-[0.85rem]'
          : 'rounded bg-muted px-1.5 py-0.5 font-mono text-[0.9em] text-foreground',
        className,
      )}
    >
      {isBlockCode && highlightedTokens && highlightedTokens.length > 0
        ? highlightedTokens.map((lineTokens, lineIndex) => (
            <Fragment key={`markdown-code-line-${lineIndex}`}>
              {lineTokens.length > 0
                ? lineTokens.map((token, tokenIndex) => (
                    <span
                      key={`markdown-code-token-${lineIndex}-${tokenIndex}`}
                      style={markdownShikiTokenStyle(token)}
                    >
                      {token.content || (tokenIndex === lineTokens.length - 1 ? ' ' : '')}
                    </span>
                  ))
                : ' '}
              {lineIndex < highlightedTokens.length - 1 ? '\n' : null}
            </Fragment>
          ))
        : children}
    </code>
  );
}

function MarkdownCheckbox({
  className,
  ...props
}: ComponentPropsWithoutRef<'input'>) {
  return <input {...props} className={cn('mr-2 align-middle', className)} />;
}

const MARKDOWN_OPTIONS = {
  disableParsingRawHTML: true,
  forceBlock: true,
  forceWrapper: true,
  wrapper: Fragment,
  overrides: {
    a: MarkdownLink,
    blockquote: {
      props: {
        className: 'mb-3 last:mb-0 border-l-2 border-border pl-4 italic text-muted-foreground',
      },
    },
    code: MarkdownCode,
    h1: {
      props: {
        className: 'mb-3 last:mb-0 text-base font-semibold text-foreground',
        style: GITHUB_MARKDOWN_HEADING_STYLE,
      },
    },
    h2: {
      props: {
        className: 'mb-3 last:mb-0 text-base font-semibold text-foreground',
        style: GITHUB_MARKDOWN_HEADING_STYLE,
      },
    },
    h3: {
      props: {
        className: 'mb-3 last:mb-0 text-sm font-semibold text-foreground',
        style: GITHUB_MARKDOWN_HEADING_STYLE,
      },
    },
    h4: {
      props: {
        className: 'mb-3 last:mb-0 text-sm font-semibold text-foreground',
        style: GITHUB_MARKDOWN_HEADING_STYLE,
      },
    },
    h5: {
      props: {
        className: 'mb-3 last:mb-0 text-sm font-semibold text-foreground',
        style: GITHUB_MARKDOWN_HEADING_STYLE,
      },
    },
    h6: {
      props: {
        className: 'mb-3 last:mb-0 text-sm font-semibold text-foreground',
        style: GITHUB_MARKDOWN_HEADING_STYLE,
      },
    },
    hr: {
      props: {
        className: 'mb-3 last:mb-0 border-border',
      },
    },
    img: {
      props: {
        className: 'mb-3 last:mb-0 max-w-full rounded-md border',
      },
    },
    input: MarkdownCheckbox,
    li: {
      props: {
        className: 'pl-1',
      },
    },
    ol: {
      props: {
        className: 'mb-3 last:mb-0 list-decimal space-y-1 pl-5',
      },
    },
    p: {
      props: {
        className: 'mb-3 last:mb-0 text-sm leading-relaxed text-foreground',
      },
    },
    pre: {
      props: {
        className:
          'mb-3 last:mb-0 overflow-x-auto rounded-md border bg-muted/60 px-3 py-3 text-xs text-foreground [&_code]:block [&_code]:whitespace-pre [&_code]:bg-transparent [&_code]:p-0 [&_code]:rounded-none',
      },
    },
    table: {
      props: {
        className: 'mb-3 last:mb-0 w-full border-collapse text-sm',
      },
    },
    td: {
      props: {
        className: 'border border-border px-2 py-1 align-top',
      },
    },
    th: {
      props: {
        className: 'border border-border bg-muted/40 px-2 py-1 text-left font-medium text-foreground',
      },
    },
    ul: {
      props: {
        className: 'mb-3 last:mb-0 list-disc space-y-1 pl-5',
      },
    },
  },
} as const;

export function MarkdownContent({
  content,
  className,
  emptyState = null,
}: MarkdownContentProps) {
  const trimmedContent = content.trim();

  if (!trimmedContent) {
    if (emptyState == null) {
      return null;
    }

    return (
      <p
        className={cn('text-sm leading-relaxed text-foreground break-words', className)}
        style={GITHUB_MARKDOWN_ROOT_STYLE}
      >
        {emptyState}
      </p>
    );
  }

  return (
    <div
      className={cn('text-sm leading-relaxed text-foreground break-words', className)}
      style={GITHUB_MARKDOWN_ROOT_STYLE}
    >
      <Markdown options={MARKDOWN_OPTIONS}>{trimmedContent}</Markdown>
    </div>
  );
}
