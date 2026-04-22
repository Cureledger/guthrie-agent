import type { Plugin } from '@elizaos/core';
import {
  type Action,
  type ActionResult,
  type HandlerCallback,
  type IAgentRuntime,
  type Memory,
  type Provider,
  type ProviderResult,
  type State,
  logger,
} from '@elizaos/core';
import { getRelevantFacts, getEntity, getEntitiesByType, guthrieKnowledgeGraph } from './knowledge.ts';

const TOPIC_KEYWORDS = [
  'pku', 'eds', 'ehlers', 'danlos', 'galactosemia', 'msud', 'maple syrup',
  'rare disease', 'newborn screening', 'rusp', 'achdnc',
  'plausible mechanism', 'fda', 'regulatory', 'cures act', 'istand', 'dct',
  'data trust', 'data sovereignty', 'privacy', 'zero-knowledge', 'zkp', 'reidentification',
  'cureledger', 'zebra reports', 'guthrie', 'robert guthrie',
  'n-of-1', 'natural history', 'real-world evidence',
  '23andme', 'henrietta lacks', 'data ownership',
  'patent', 'mars metro', 'compliance', 'validation key',
  'lenmeldy', 'mld', 'leukodystrophy',
  'consent', 'hipaa', 'gdpr', 'part 11',
  'fhir', 'cdisc', 'loinc',
  'affiliate', 'investor', 'token', 'cures-usa',
];

function extractTopics(text: string): string[] {
  const lower = text.toLowerCase();
  return TOPIC_KEYWORDS.filter((kw) => lower.includes(kw));
}

/**
 * Disorder lookup action — returns structured info for a given rare disease
 * from the knowledge graph.
 */
const disorderLookupAction: Action = {
  name: 'DISORDER_LOOKUP',
  similes: ['FIND_DISORDER', 'SEARCH_DISEASE', 'RARE_DISEASE_INFO'],
  description: 'Looks up structured information about a rare disease or disorder from the knowledge graph',

  validate: async (_runtime: IAgentRuntime, message: Memory, _state: State): Promise<boolean> => {
    const text = (message.content?.text || '').toLowerCase();
    return (
      text.includes('disorder') ||
      text.includes('disease') ||
      text.includes('syndrome') ||
      text.includes('pku') ||
      text.includes('eds') ||
      text.includes('galactosemia') ||
      text.includes('msud') ||
      text.includes('phenylketonuria') ||
      text.includes('ehlers')
    );
  },

  handler: async (
    _runtime: IAgentRuntime,
    message: Memory,
    _state: State,
    _options: unknown,
    callback: HandlerCallback,
  ): Promise<ActionResult> => {
    const query = (message.content?.text || '').toLowerCase();
    logger.info({ query }, 'Disorder lookup requested');

    const disorderEntities = getEntitiesByType('disorder').concat(getEntitiesByType('disorder_family'));

    const matched = disorderEntities.filter((entity) => {
      const name = entity.name.toLowerCase();
      const abbr = (entity.properties.abbreviation || '').toLowerCase();
      return query.includes(name) || query.includes(abbr) || (abbr && query.includes(abbr));
    });

    if (matched.length > 0) {
      const info = matched
        .map((entity) => {
          const props = entity.properties;
          const lines = [`**${entity.name}**${props.abbreviation ? ` (${props.abbreviation})` : ''}`];
          if (entity.description) lines.push(entity.description);
          if (props.prevalence) lines.push(`Prevalence: ${props.prevalence}`);
          if (props.inheritance) lines.push(`Inheritance: ${props.inheritance}`);
          if (props.gene) lines.push(`Gene: ${props.gene}`);
          if (props.subtypes) lines.push(`Subtypes: ${props.subtypes}`);
          if (props.screened_at_birth !== undefined)
            lines.push(`Screened at birth: ${props.screened_at_birth ? 'Yes' : 'No'}`);
          if (props.rusp) lines.push('On RUSP: Yes');
          if (props.comorbidities) lines.push(`Common comorbidities: ${props.comorbidities.join(', ')}`);
          return lines.join('\n');
        })
        .join('\n\n');

      const topics = extractTopics(query);
      const relatedFacts = getRelevantFacts(topics);
      const factsSection = relatedFacts.length > 0 ? `\n\nRelated context:\n${relatedFacts.map((f) => `- ${f}`).join('\n')}` : '';

      await callback({
        text: `${info}${factsSection}`,
        action: 'DISORDER_LOOKUP',
      });
    } else {
      const topics = extractTopics(query);
      const facts = getRelevantFacts(topics);

      await callback({
        text:
          facts.length > 0
            ? `I don't have a specific disorder profile for that, but here's what I know:\n${facts.map((f) => `- ${f}`).join('\n')}`
            : `I don't have detailed data on that specific disorder yet. Cureledger's rare disease knowledge base is expanding — currently covering ${disorderEntities.length} conditions in detail. Can I help with PKU, EDS, galactosemia, or MSUD?`,
        action: 'DISORDER_LOOKUP',
      });
    }

    return { success: true, text: 'Disorder lookup executed' };
  },
};

/**
 * Context provider that injects topic-matched rare disease facts
 * from the knowledge graph into every conversation.
 */
const rareDiseaseContextProvider: Provider = {
  name: 'RARE_DISEASE_CONTEXT',
  description: 'Provides relevant Cureledger/rare disease context matched to conversation topics',

  get: async (_runtime: IAgentRuntime, message: Memory): Promise<ProviderResult> => {
    const text = message.content?.text || '';
    const topics = extractTopics(text);

    if (topics.length === 0) {
      return {
        text: `Context: Guthrie is the community agent for Cureledger, a patient-sovereign rare disease data platform by Cureledger Inc. Cureledger launches with two verticals — Ehlers-Danlos Syndrome (community reach) and newborn screening disorders starting with PKU (clinical seriousness, advocacy gap from ACHDNC termination in April 2025). 30M Americans have rare diseases; 95% lack FDA-approved treatments. Zebra Reports (zebrareports.com) is the Shopify storefront covering EDS and newborn-screening-disorder products; affiliate revenue funds the platform. The Cureledger data package system uses zero-knowledge proofs for patient data sovereignty.`,
      };
    }

    const facts = getRelevantFacts(topics);

    const entityHits: string[] = [];
    for (const entity of Object.values(guthrieKnowledgeGraph.entities)) {
      const entityLower = entity.name.toLowerCase();
      if (topics.some((t) => entityLower.includes(t) || t.includes(entityLower))) {
        if (entity.description) {
          entityHits.push(`${entity.name}: ${entity.description}`);
        }
      }
    }

    const parts: string[] = [];
    if (entityHits.length > 0) parts.push(`Entities:\n${entityHits.join('\n')}`);
    if (facts.length > 0) parts.push(`Facts:\n${facts.join('\n')}`);

    return {
      text: parts.length > 0 ? `Relevant context:\n${parts.join('\n\n')}` : '',
    };
  },
};

const guthriePlugin: Plugin = {
  name: 'guthrie-plugin',
  description: 'Cureledger platform actions: disorder lookup, knowledge-graph-backed context',
  actions: [disorderLookupAction],
  providers: [rareDiseaseContextProvider],
};

export default guthriePlugin;
