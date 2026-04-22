/**
 * Canonical facts and links for Guthrie.
 *
 * Positive knowledge only: entities the agent may cite. Refusals and funnel
 * behavior live in scope.ts and character.ts, not here.
 *
 * All user-facing URLs must be absolute (see urls.ts). Do not use /#join or /blog in facts.
 */

import { cureledgerUrl } from "./urls.ts";

export interface KnowledgeEntity {
  id: string;
  type: string;
  name: string;
  properties: Record<string, unknown>;
  description?: string;
}

export interface KnowledgeRelationship {
  from: string;
  to: string;
  type: string;
  properties?: Record<string, unknown>;
}

export interface KnowledgeGraph {
  entities: Record<string, KnowledgeEntity>;
  relationships: KnowledgeRelationship[];
  facts: string[];
}

/**
 * Override with env when the whitepaper ships at a different path.
 * Default is a real site URL (page may 404 until published).
 */
export const WHITEPAPER_URL: string | null =
  process.env.CURELEDGER_WHITEPAPER_URL?.trim() || cureledgerUrl.whitepaper;

export const guthrieKnowledgeGraph: KnowledgeGraph = {
  entities: {
    Cureledger: {
      id: "Cureledger",
      type: "platform",
      name: "Cureledger",
      properties: {
        operator: "Cureledger Inc.",
        incorporation: "Delaware C-Corp",
        patent: "US 12,095,919 B2",
        mission:
          "Patient-driven: help rare disease families own and benefit from their longitudinal data. Privacy-by-design, fiduciary-grade custody, patient-controlled reuse.",
        founder_background: `Nina Kilbride: rare disease parent; attorney; Series 65-qualified legal software engineer; practiced law in Raleigh-Durham; taught herself to code; building since 2015 toward financial-grade rare disease data marketplaces and AI that can use longitudinal data where legacy drug development cannot. Long-form founder story: ${cureledgerUrl.founderStory}.`,
        name_rationale:
          "The name reflects a patient-driven mission to advance therapies for conditions that are hard to monetize under legacy models.",
      },
      description:
        "Cureledger builds privacy-by-design systems so patient-owned data can fuel research without the usual extraction story. Patients own the data; Cureledger Inc. is custodian and trustee.",
    },

    ZebraReports: {
      id: "ZebraReports",
      type: "product",
      name: "Zebra Reports",
      properties: {
        url: cureledgerUrl.zebraReports,
        role: "Community product reviews and storefront (EDS and newborn-screening-related categories).",
        note: "Point users here for reviews, not specific product picks in chat.",
      },
      description:
        "Cureledger-affiliated reviews and commerce. Affiliate revenue can support platform work. Not a substitute for clinical advice.",
    },

    DataTrust: {
      id: "DataTrust",
      type: "legal_structure",
      name: "Fiduciary-grade data trust",
      properties: {
        ownership: "Patients own their data.",
        custodian: "Cureledger Inc. acts as custodian and trustee, not owner.",
        design_goals: ["privacy-by-design", "constructive reuse with patient benefit", "withdrawal rights"],
      },
      description:
        "Structured so user data is held for users benefit in a fiduciary posture, distinct from models where corporate bankruptcy treats patient data as a generic asset.",
    },

    CanonicalLinks: {
      id: "CanonicalLinks",
      type: "urls",
      name: "Site and content links",
      properties: {
        marketing_base: cureledgerUrl.home,
        email_signup: cureledgerUrl.emailSignup,
        blog: cureledgerUrl.blog,
        fda_comment: cureledgerUrl.fdaComment,
        founder_story: cureledgerUrl.founderStory,
        whitepaper_page: cureledgerUrl.whitepaper,
        whitepaper_pdf: cureledgerUrl.whitepaperPdf,
        whitepaper_url: WHITEPAPER_URL,
      },
      description:
        "In all chat replies use these absolute URLs exactly. Email: email_signup. Whitepaper: whitepaper_page (read online) and whitepaper_pdf (download). Investor depth: whitepaper_url or whitepaper_pdf.",
    },

    DataCollectionFocus: {
      id: "DataCollectionFocus",
      type: "scope",
      name: "Current data and community focus",
      properties: {
        includes: [
          "Ehlers-Danlos Syndrome (community and reviews context)",
          "Disorders on the typical US newborn screening panel (systemic context, not clinical teaching)",
        ],
        clinical_detail: "Keep minimal in chat. Defer to blog and Zebra Reports for depth.",
      },
      description:
        "Guthrie is a funnel agent, not a pathology tutor. Answer in plain language, then point to the blog and signup when useful.",
    },

    RegulatoryPublic: {
      id: "RegulatoryPublic",
      type: "regulatory",
      name: "Public regulatory touchpoints",
      properties: {
        fda_comment:
          "Cureledger filed public comment on the FDA Plausible Mechanism Framework draft guidance.",
        pmf:
          "Draft FDA framework relevant to individualized and small-population evidence; cite blog, do not give legal advice.",
        rwe: "Real-world evidence and natural history data are increasingly recognized in FDA thinking.",
        cures_act: "21st Century Cures Act helped formalize RWE pathways.",
        istand: "ISTAND pilot relates to novel biomarker qualification.",
      },
      description: "High-level pointers. Details belong in blog posts and formal filings.",
    },

    ScreeningHistory: {
      id: "ScreeningHistory",
      type: "history",
      name: "Newborn screening",
      properties: {
        robert_guthrie: "Robert Guthrie developed the heel-prick screening approach (1963), foundational for PKU screening and expanded panels.",
        rusp: "Recommended Uniform Screening Panel lists core screening targets in the US.",
        achdnc:
          "ACHDNC was the federal advisory committee for newborn screening panel updates; terminated April 2025 (fact only, no political editorializing).",
      },
      description: "Historical and structural context, not a clinical guide.",
    },

    RobertGuthrie: {
      id: "RobertGuthrie",
      type: "person",
      name: "Robert Guthrie",
      properties: {
        lifespan: "1916–1995",
        contribution: "Microbiologist; newborn screening heel-prick test (1963).",
      },
      description: "Namesake for the Guthrie agent.",
    },

    NinaKilbride: {
      id: "NinaKilbride",
      type: "person",
      name: "Nina Kilbride",
      properties: {
        role: "Founder",
        credentials:
          "Attorney; Series 65-qualified legal software engineer; practiced law in Raleigh-Durham.",
        founder_story_url: cureledgerUrl.founderStory,
      },
      description:
        `Started Cureledger. Rare disease parent; saw how drug development incentives favor common conditions while leaving rare but treatable disorders behind. Self-taught developer since 2015. Full narrative: ${cureledgerUrl.founderStory}.`,
    },

    Whitepaper: {
      id: "Whitepaper",
      type: "document",
      name: "Cureledger Whitepaper April 2026",
      properties: {
        title: "Cureledger: The Data Layer for Rare Disease Drug Development",
        period: "April 2026",
        page_url: cureledgerUrl.whitepaper,
        pdf_url: cureledgerUrl.whitepaperPdf,
      },
      description:
        `Full strategic document (thesis, Life Data Trust, Plausible Mechanism Framework, market, moat, patents). Complete markdown is injected for Guthrie via the WHITEPAPER_FULL provider. Links: ${cureledgerUrl.whitepaper} and PDF ${cureledgerUrl.whitepaperPdf}.`,
    },
  },

  relationships: [
    { from: "NinaKilbride", to: "Cureledger", type: "founded" },
    { from: "Cureledger", to: "Whitepaper", type: "documented_in" },
    { from: "Cureledger", to: "ZebraReports", type: "operates" },
    { from: "Cureledger", to: "DataTrust", type: "implements" },
    { from: "RobertGuthrie", to: "ScreeningHistory", type: "associated_with" },
    { from: "Cureledger", to: "RegulatoryPublic", type: "participates_in" },
    { from: "Cureledger", to: "DataCollectionFocus", type: "focuses_on" },
  ],

  facts: [
    `Primary CTAs (use these full URLs in replies): email and launch interest ${cureledgerUrl.emailSignup}; blog ${cureledgerUrl.blog}; FDA comment ${cureledgerUrl.fdaComment}; founder story ${cureledgerUrl.founderStory}; whitepaper page ${cureledgerUrl.whitepaper}; whitepaper PDF ${cureledgerUrl.whitepaperPdf}. Zebra Reports ${cureledgerUrl.zebraReports}.`,
    "Globally, roughly 300 million people live with rare diseases; thousands of distinct conditions.",
    "Living with a rare disease often means diagnostic mystery, isolation, and cost that common-disease care does not mirror.",
    "Modern systems can capture far more patient-generated and longitudinal data than classic trials alone. AI is only as good as its inputs and governance.",
    "FDA policy has moved toward frameworks that value real-world evidence and natural history where appropriate.",
    "Historically, patients often saw little return from contributing detailed data about themselves. Cureledger aims to change incentives and custody so contributors can benefit.",
    "Rare disease families have often been the ones who push solutions through when institutional incentives lag.",
    "Users can contribute multiple kinds of relevant data under a privacy-by-design approach. Data is held in a fiduciary-grade posture so reuse can benefit contributors, not only intermediaries.",
    "The design targets both a 23andMe-style custody-in-bankruptcy failure mode and a Henrietta Lacks-style exploitation pattern at a systems level (not legal advice).",
    "HIPAA Safe Harbor de-identification is often weak for ultra-small cohorts where the disease itself is identifying; this is a known limitation discussed in public regulatory comment.",
    "Cureledger Inc. is a Delaware corporation. US Patent 12,095,919 B2 relates to zero-knowledge and record-handling methods in scope of the platform narrative.",
    `For investors: rare disease is a credible wedge into AI plus verifiable patient data at massive scale. No round, valuation, or instrument in chat. Use ${cureledgerUrl.fdaComment}, whitepaper at ${WHITEPAPER_URL}, and ${cureledgerUrl.emailSignup}.`,
    `Founder Nina Kilbride: rare disease parent, attorney, Series 65-qualified legal software engineer, practiced law in Raleigh-Durham, coding since 2015 toward patient sovereignty and financial-grade rare disease data marketplaces. Essay: ${cureledgerUrl.founderStory}.`,
    "Focus for data and community (systemic only, not clinical teaching): Ehlers-Danlos Syndrome and disorders on the typical US newborn screening panel. Point to blog and Zebra Reports for depth.",
  ],
};

export function getRelevantFacts(topics: string[]): string[] {
  const topicLower = topics.map(t => t.toLowerCase());
  return guthrieKnowledgeGraph.facts.filter(fact => {
    const factLower = fact.toLowerCase();
    return topicLower.some(topic => factLower.includes(topic));
  });
}

export function getEntity(nameOrId: string): KnowledgeEntity | undefined {
  return guthrieKnowledgeGraph.entities[nameOrId];
}

export function getEntitiesByType(type: string): KnowledgeEntity[] {
  return Object.values(guthrieKnowledgeGraph.entities).filter(
    entity => entity.type === type,
  );
}
