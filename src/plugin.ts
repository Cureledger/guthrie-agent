import type { Plugin } from '@elizaos/core';
import type { IAgentRuntime, Memory, Provider, ProviderResult } from '@elizaos/core';
import { getRelevantFacts, guthrieKnowledgeGraph } from './knowledge.ts';
import { getWhitepaperFullText } from './whitepaper.ts';
import { cureledgerUrl } from './urls.ts';

const TOPIC_KEYWORDS = [
  'data',
  'collect',
  'contribute',
  'pku',
  'eds',
  'ehlers',
  'danlos',
  'rare disease',
  'newborn screening',
  'rusp',
  'achdnc',
  'plausible mechanism',
  'fda',
  'regulatory',
  'cures act',
  'istand',
  'data trust',
  'data sovereignty',
  'privacy',
  'cureledger',
  'zebra reports',
  'guthrie',
  'robert guthrie',
  'natural history',
  'real-world evidence',
  '23andme',
  'henrietta',
  'investor',
  'invest',
  'founder',
  'nina',
  'kilbride',
  'whitepaper',
  'hipaa',
  'patent',
];

function extractTopics(text: string): string[] {
  const lower = text.toLowerCase();
  return TOPIC_KEYWORDS.filter(kw => lower.includes(kw));
}

/**
 * Topic-matched facts for the model. No keyword-gated action overrides the LLM:
 * the general model infers funnel; this only supplies canonical facts.
 */
const rareDiseaseContextProvider: Provider = {
  name: 'RARE_DISEASE_CONTEXT',
  description: 'Topic-matched facts from the canonical knowledge list',

  get: async (_runtime: IAgentRuntime, message: Memory): Promise<ProviderResult> => {
    const text = message.content?.text || '';
    const topics = extractTopics(text);

    if (topics.length === 0) {
      return {
        text: `Context for Guthrie: Cureledger community agent. Tone: conversational, direct, not product-spec jargon. Use full URLs only: email ${cureledgerUrl.emailSignup}, blog ${cureledgerUrl.blog}, FDA comment ${cureledgerUrl.fdaComment}. Do not invent fundraising detail. High-level disease focus: EDS and US newborn screening panel conditions only (systemic, not clinical teaching).`,
      };
    }

    const facts = getRelevantFacts(topics);

    const entityHits: string[] = [];
    for (const entity of Object.values(guthrieKnowledgeGraph.entities)) {
      const entityLower = entity.name.toLowerCase();
      if (topics.some(t => entityLower.includes(t) || t.includes(entityLower))) {
        if (entity.description) {
          entityHits.push(`${entity.name}: ${entity.description}`);
        }
      }
    }

    const parts: string[] = [];
    if (entityHits.length > 0) parts.push(`Entities:\n${entityHits.join('\n')}`);
    if (facts.length > 0) parts.push(`Facts:\n${facts.join('\n')}`);

    return {
      text:
        parts.length > 0
          ? `Relevant context (paraphrase in conversational marketing voice, do not paste as bullets; use full URLs from facts when you link):\n${parts.join('\n\n')}`
          : '',
    };
  },
};

/** Injecting ~40k+ chars of whitepaper on every turn blows past context limits and breaks the LLM. Full text only when the user clearly needs it. */
function shouldAttachFullWhitepaper(messageText: string): boolean {
  if (process.env.GUTHRIE_ALWAYS_ATTACH_WHITEPAPER === "1") return true;
  const t = messageText.toLowerCase();
  const triggers = [
    "whitepaper",
    "full document",
    "full paper",
    "thesis",
    "life data trust",
    "plausible mechanism",
    " pmf",
    "pmf,",
    "moat",
    "fiduciary",
    "part i",
    "part ii",
    "part iii",
    "part iv",
    "part v",
    "appendix",
    "executive summary",
    "data layer",
    "pro rata",
    "trust architecture",
    "section 3",
    "section 4",
    "section 5",
  ];
  return triggers.some(k => t.includes(k));
}

/**
 * Whitepaper: full markdown only when triggers match (otherwise URLs + pointer only).
 */
const whitepaperKnowledgeProvider: Provider = {
  name: "WHITEPAPER_FULL",
  description:
    "Cureledger whitepaper (April 2026): full text when relevant, otherwise links only",

  get: async (_runtime: IAgentRuntime, message: Memory): Promise<ProviderResult> => {
    const userText = message.content?.text || "";
    const meta = `Cureledger whitepaper (April 2026). Read online: ${cureledgerUrl.whitepaper} | PDF: ${cureledgerUrl.whitepaperPdf}. Ground investor or architecture answers in this document when the user asks about thesis, trust, PMF, or market.`;

    if (!shouldAttachFullWhitepaper(userText)) {
      return { text: meta };
    }

    try {
      const body = getWhitepaperFullText();
      return {
        text: `${meta}\n\n---\nFULL WHITEPAPER (INTERNAL — summarize for chat; do not dump unless asked)\n---\n\n${body}`,
      };
    } catch {
      return {
        text: `Whitepaper file missing on this server. Link users to ${cureledgerUrl.whitepaper} or ${cureledgerUrl.whitepaperPdf}.`,
      };
    }
  },
};

const guthriePlugin: Plugin = {
  name: 'guthrie-plugin',
  description: 'Cureledger: knowledge-backed context for the LLM (no keyword action overrides)',
  providers: [rareDiseaseContextProvider, whitepaperKnowledgeProvider],
};

export default guthriePlugin;
