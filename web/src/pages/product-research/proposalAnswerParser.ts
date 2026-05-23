export type ProposalAnswerSectionKey =
  | 'problemOpportunity'
  | 'userBusinessImpact'
  | 'repositoryEvidence'
  | 'externalEvidence'
  | 'proposedScope'
  | 'nonGoals'
  | 'risksMitigations'
  | 'suggestedSmallFeatureBreakdown'
  | 'openQuestions';

export type ProposalAnswerSectionTab =
  | 'decision-brief'
  | 'evidence'
  | 'scope'
  | 'risks'
  | 'breakdown'
  | 'open-questions'
  | 'full-text';

export type ProposalAnswerParseStatus = 'parsed' | 'empty' | 'unrecognized';

export type ProposalAnswerSections = Partial<Record<ProposalAnswerSectionKey, string>>;

export type ParsedProposalAnswer = {
  fullText: string;
  sections: ProposalAnswerSections;
  status: ProposalAnswerParseStatus;
  unrecognizedContent: string;
};

const SECTION_ALIASES: Record<string, ProposalAnswerSectionKey> = {
  'Problem / Opportunity': 'problemOpportunity',
  'User / Business Impact': 'userBusinessImpact',
  'Repository Evidence': 'repositoryEvidence',
  'External Evidence': 'externalEvidence',
  'Proposed Scope': 'proposedScope',
  'Non-Goals': 'nonGoals',
  'Risks & Mitigations': 'risksMitigations',
  'Suggested Small Feature Breakdown': 'suggestedSmallFeatureBreakdown',
  'Open Questions': 'openQuestions',
};

const NORMALIZED_SECTION_ALIASES = new Map(
  Object.entries(SECTION_ALIASES).map(([heading, key]) => [normalizeHeading(heading), key]),
);

export const SECOND_LEVEL_HEADING_PATTERN = /^##(?!#)\s+(.+)\s*$/;

export function parseProposalAnswerSections(answer: string): ParsedProposalAnswer {
  const fullText = answer ?? '';

  if (!fullText.trim()) {
    return { fullText, sections: {}, status: 'empty', unrecognizedContent: '' };
  }

  const sections: ProposalAnswerSections = {};
  const unrecognizedBlocks: string[] = [];
  let currentKey: ProposalAnswerSectionKey | null = null;
  let currentHeading: string | null = null;
  let currentLines: string[] = [];

  const flush = () => {
    const content = currentLines.join('\n').trim();
    if (!content && !currentHeading) return;
    if (currentKey) {
      sections[currentKey] = content;
    } else {
      unrecognizedBlocks.push([currentHeading, content].filter(Boolean).join('\n').trim());
    }
  };

  for (const line of fullText.split(/\r?\n/)) {
    const match = line.match(SECOND_LEVEL_HEADING_PATTERN);
    if (match) {
      flush();
      currentHeading = line.trim();
      currentKey = NORMALIZED_SECTION_ALIASES.get(normalizeHeading(match[1])) ?? null;
      currentLines = [];
      continue;
    }
    currentLines.push(line);
  }
  flush();

  const status = Object.keys(sections).length > 0 ? 'parsed' : 'unrecognized';
  return { fullText, sections, status, unrecognizedContent: unrecognizedBlocks.join('\n\n') };
}

function normalizeHeading(heading: string) {
  return heading.replace(/[*_`#]/g, '').replace(/\s+/g, ' ').trim().toLowerCase();
}
