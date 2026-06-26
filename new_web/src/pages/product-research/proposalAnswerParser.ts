type ProposalAnswerSections = {
  problemOpportunity?: string;
  proposedScope?: string;
  suggestedSmallFeatureBreakdown?: string;
  userBusinessImpact?: string;
};

type ProposalAnswer = {
  sections: ProposalAnswerSections;
};

export function parseProposalAnswerSections(answer: string): ProposalAnswer {
  if (!answer?.trim()) {
    return { sections: {} };
  }

  const sections: ProposalAnswerSections = {};
  const lines = answer.split('\n');
  let currentSection: keyof ProposalAnswerSections | null = null;
  let currentContent: string[] = [];

  const sectionPatterns: Array<{ key: keyof ProposalAnswerSections; pattern: RegExp }> = [
    { key: 'problemOpportunity', pattern: /problem|opportunity|background|context/i },
    { key: 'proposedScope', pattern: /scope|proposal|approach|solution/i },
    { key: 'suggestedSmallFeatureBreakdown', pattern: /feature|breakdown|plan|step|implementation/i },
    { key: 'userBusinessImpact', pattern: /impact|value|benefit|user|business/i },
  ];

  for (const line of lines) {
    const headingMatch = line.match(/^#{1,3}\s+(.+)$/);
    if (headingMatch) {
      if (currentSection && currentContent.length > 0) {
        sections[currentSection] = currentContent.join('\n').trim();
      }

      const headingText = headingMatch[1];
      currentSection = null;
      for (const sp of sectionPatterns) {
        if (sp.pattern.test(headingText)) {
          currentSection = sp.key;
          break;
        }
      }
      currentContent = [];
    } else {
      currentContent.push(line);
    }
  }

  if (currentSection && currentContent.length > 0) {
    sections[currentSection] = currentContent.join('\n').trim();
  }

  if (Object.keys(sections).length === 0) {
    sections.problemOpportunity = answer.trim();
  }

  return { sections };
}
