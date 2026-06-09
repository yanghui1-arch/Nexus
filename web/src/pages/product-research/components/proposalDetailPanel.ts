export type ProposalDetailTabKey =
  | 'overview'
  | 'scope'
  | 'evidence'
  | 'risk'
  | 'breakdown'
  | 'description'
  | 'plan-list';

export type ProposalOverviewItem = {
  content: string | undefined;
  label: string;
};

export function combineProposalSections(...sections: Array<string | undefined>) {
  return sections.filter(section => section?.trim()).join('\n\n');
}

export function summarizeProposalLine(content: string | undefined, fallback: string) {
  const plainText = content
    ?.replace(/[#*_`>\-[\]()]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
  if (!plainText) {
    return fallback;
  }
  return plainText.length > 140 ? `${plainText.slice(0, 137)}…` : plainText;
}
