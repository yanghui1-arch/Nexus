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
export type ProposalAnswerSectionMap = Partial<Record<ProposalAnswerSectionKey, string>>;
export type ProposalAnswerParseStatus = 'empty' | 'parsed' | 'partial' | 'unrecognized';
export type ProposalAnswerParseResult = {
  sections: ProposalAnswerSectionMap;
  fullText: string;
  unrecognizedContent: string;
  status: ProposalAnswerParseStatus;
};

const SECTION_ALIASES: Record<string, ProposalAnswerSectionKey> = {
  problem: 'problemOpportunity',
  opportunity: 'problemOpportunity',
  problemopportunity: 'problemOpportunity',
  userbusinessimpact: 'userBusinessImpact',
  businessimpact: 'userBusinessImpact',
  userimpact: 'userBusinessImpact',
  repositoryevidence: 'repositoryEvidence',
  repoevidence: 'repositoryEvidence',
  externalevidence: 'externalEvidence',
  proposedscope: 'proposedScope',
  scope: 'proposedScope',
  nongoals: 'nonGoals',
  outofscope: 'nonGoals',
  risksmitigations: 'risksMitigations',
  risks: 'risksMitigations',
  mitigations: 'risksMitigations',
  suggestedsmallfeaturebreakdown: 'suggestedSmallFeatureBreakdown',
  smallfeaturebreakdown: 'suggestedSmallFeatureBreakdown',
  featurebreakdown: 'suggestedSmallFeatureBreakdown',
  openquestions: 'openQuestions',
  questions: 'openQuestions',
};
const SECOND_LEVEL_HEADING_PATTERN = /^##(?!#)\s+(.+?)\s*#*\s*$/;

export function parseProposalAnswerSections(
  answer: string | null | undefined,
): ProposalAnswerParseResult {
  const fullText = answer ?? '';
  if (!fullText.trim()) {
    return { sections: {}, fullText, unrecognizedContent: '', status: 'empty' };
  }

  const sections: ProposalAnswerSectionMap = {};
  const unrecognizedParts: string[] = [];
  let currentKey: ProposalAnswerSectionKey | null = null;
  let currentHeading: string | null = null;
  let currentLines: string[] = [];
  const flush = () => {
    const content = currentLines.join('\n').trim();
    if (currentKey) {
      sections[currentKey] = sections[currentKey]
        ? [sections[currentKey], content].filter(Boolean).join('\n\n')
        : content;
    } else if (currentHeading || content) {
      unrecognizedParts.push([currentHeading ? `## ${currentHeading}` : '', content]
        .filter(Boolean).join('\n').trim());
    }
  };

  for (const line of fullText.split(/\r?\n/)) {
    const headingMatch = line.match(SECOND_LEVEL_HEADING_PATTERN);
    if (headingMatch) {
      flush();
      currentHeading = headingMatch[1].trim();
      currentKey = SECTION_ALIASES[normalizeHeading(currentHeading)] ?? null;
      currentLines = [];
    } else {
      currentLines.push(line);
    }
  }
  flush();

  const recognizedCount = Object.keys(sections).length;
  const unrecognizedContent = unrecognizedParts.filter(Boolean).join('\n\n').trim();
  const status = recognizedCount === 0
    ? 'unrecognized'
    : unrecognizedContent
      ? 'partial'
      : 'parsed';
  return { sections, fullText, unrecognizedContent, status };
}

function normalizeHeading(heading: string): string {
  return heading
    .replace(/[`*_~[\]()]/g, '')
    .replace(/&|\band\b/gi, '')
    .replace(/[^a-z0-9]/gi, '')
    .toLowerCase();
}
