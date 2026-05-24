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
  overview: 'problemOpportunity',
  summary: 'problemOpportunity',
  background: 'problemOpportunity',
  proposaloverview: 'problemOpportunity',
  概览: 'problemOpportunity',
  背景: 'problemOpportunity',
  问题: 'problemOpportunity',
  机会: 'problemOpportunity',
  problem: 'problemOpportunity',
  opportunity: 'problemOpportunity',
  problemopportunity: 'problemOpportunity',
  userbusinessimpact: 'userBusinessImpact',
  businessimpact: 'userBusinessImpact',
  userimpact: 'userBusinessImpact',
  value: 'userBusinessImpact',
  impact: 'userBusinessImpact',
  价值: 'userBusinessImpact',
  收益: 'userBusinessImpact',
  影响: 'userBusinessImpact',
  evidence: 'repositoryEvidence',
  repositoryevidence: 'repositoryEvidence',
  repoevidence: 'repositoryEvidence',
  codeevidence: 'repositoryEvidence',
  证据: 'repositoryEvidence',
  代码证据: 'repositoryEvidence',
  仓库证据: 'repositoryEvidence',
  externalevidence: 'externalEvidence',
  marketevidence: 'externalEvidence',
  proposedscope: 'proposedScope',
  scope: 'proposedScope',
  range: 'proposedScope',
  范围: 'proposedScope',
  实施范围: 'proposedScope',
  nongoals: 'nonGoals',
  outofscope: 'nonGoals',
  非目标: 'nonGoals',
  不做: 'nonGoals',
  risksmitigations: 'risksMitigations',
  risks: 'risksMitigations',
  mitigations: 'risksMitigations',
  risk: 'risksMitigations',
  风险: 'risksMitigations',
  风险缓解: 'risksMitigations',
  suggestedsmallfeaturebreakdown: 'suggestedSmallFeatureBreakdown',
  smallfeaturebreakdown: 'suggestedSmallFeatureBreakdown',
  featurebreakdown: 'suggestedSmallFeatureBreakdown',
  breakdown: 'suggestedSmallFeatureBreakdown',
  split: 'suggestedSmallFeatureBreakdown',
  plan: 'suggestedSmallFeatureBreakdown',
  拆分: 'suggestedSmallFeatureBreakdown',
  功能拆分: 'suggestedSmallFeatureBreakdown',
  实施计划: 'suggestedSmallFeatureBreakdown',
  openquestions: 'openQuestions',
  questions: 'openQuestions',
  待确认: 'openQuestions',
};
const ANY_MARKDOWN_HEADING_PATTERN = /^#{1,6}\s+(.+?)\s*#*\s*$/;

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
    const headingMatch = line.match(ANY_MARKDOWN_HEADING_PATTERN);
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
    .replace(/^(\d+[.)、-]?|[一二三四五六七八九十]+[、.．])\s*/u, '')
    .replace(/[：:]+$/u, '')
    .replace(/[^\p{L}\p{N}]/gu, '')
    .toLowerCase();
}
