const BRIEF_SECTIONS = {
  problem: 'Problem / Opportunity',
  impact: 'User & Business Impact',
  evidence: 'Repository Evidence',
  scope: 'Proposed Scope',
  risks: 'Risks & Mitigations',
  nextSteps: 'Suggested Small-feature Breakdown',
} as const;

export type BriefSectionKey = keyof typeof BRIEF_SECTIONS;

export function getProposalBriefSections(answer: string): Record<BriefSectionKey, string> {
  const sections: Partial<Record<BriefSectionKey, string[]>> = {};
  let current: BriefSectionKey | null = null;

  answer.split(/\r?\n/).forEach(line => {
    const heading = line.match(/^##\s+(.+)$/);
    if (heading) {
      current = (Object.entries(BRIEF_SECTIONS).find(
        ([, title]) => title === heading[1].trim(),
      )?.[0] as BriefSectionKey | undefined) ?? null;
      if (current) {
        sections[current] = [];
      }
      return;
    }
    if (current) {
      sections[current]?.push(line);
    }
  });

  return Object.fromEntries(
    Object.keys(BRIEF_SECTIONS).map(key => [
      key,
      sections[key as BriefSectionKey]?.join('\n').trim() ?? '',
    ]),
  ) as Record<BriefSectionKey, string>;
}

export function getFirstMeaningfulLine(content: string | undefined): string | null {
  const line = content
    ?.split(/\r?\n/)
    .map(item => item.replace(/^[-*\d.)\s]+/, '').trim())
    .find(Boolean);
  return line || null;
}
