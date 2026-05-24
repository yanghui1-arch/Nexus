import { parseProposalAnswerSections } from './proposalAnswerParser';

export type BriefSectionKey =
  | 'problem'
  | 'impact'
  | 'evidence'
  | 'scope'
  | 'risks'
  | 'nextSteps';

export function getProposalBriefSections(answer: string): Record<BriefSectionKey, string> {
  const { sections } = parseProposalAnswerSections(answer);
  return {
    problem: sections.problemOpportunity ?? '',
    impact: sections.userBusinessImpact ?? '',
    evidence: sections.repositoryEvidence ?? '',
    scope: sections.proposedScope ?? '',
    risks: sections.risksMitigations ?? '',
    nextSteps: sections.suggestedSmallFeatureBreakdown ?? '',
  };
}

export function getFirstMeaningfulLine(content: string | undefined): string | null {
  const line = content
    ?.split(/\r?\n/)
    .map(item => item.replace(/^[-*\d.)\s]+/, '').trim())
    .find(Boolean);
  return line || null;
}
