/**
 * Guthrie Platform Knowledge Graph
 *
 * Structured knowledge base for rare disease data infrastructure.
 * Covers disorders, regulatory pathways, data architecture, and the
 * Zebra Reports product ecosystem.
 */

export interface KnowledgeEntity {
  id: string;
  type: string;
  name: string;
  properties: Record<string, any>;
  description?: string;
}

export interface KnowledgeRelationship {
  from: string;
  to: string;
  type: string;
  properties?: Record<string, any>;
}

export interface KnowledgeGraph {
  entities: Record<string, KnowledgeEntity>;
  relationships: KnowledgeRelationship[];
  facts: string[];
}

export const guthrieKnowledgeGraph: KnowledgeGraph = {
  entities: {
    "Cureledger": {
      id: "Cureledger",
      type: "platform",
      name: "Cureledger",
      properties: {
        operator: "Cureledger Inc.",
        incorporation: "Delaware C-Corp",
        patent: "US 12,095,919 B2",
        mission: "patient-sovereign rare disease data infrastructure",
        verticals: ["Ehlers-Danlos Syndrome (EDS)", "newborn screening disorders (starting with PKU)"],
        strategy: "two-vertical launch. EDS for community reach. Newborn screening (starting with PKU) for clinical seriousness and well-characterized natural history.",
        origin: "Built over more than a decade by a founder with a combined background in law, fintech development, and parenting a child with a rare disease.",
        design_principles: "Human-centric, ethical, privacy-by-design. Patients own their data at every step.",
      },
      description: "Patient-sovereign rare disease data platform. Patients own, govern, and benefit from their health data. Operated by Cureledger Inc. Guthrie is the community-facing agent for Cureledger.",
    },
    "ZebraReports": {
      id: "ZebraReports",
      type: "product",
      name: "Zebra Reports",
      properties: {
        url: "zebrareports.com",
        platform: "Shopify",
        role: "consumer review platform and storefront",
        funding: "affiliate revenue (Amazon Associates + brand-direct)",
        affiliate_tag: "zebrareports-20",
        product_categories: [
          "EDS: braces, compression garments, mobility aids",
          "newborn screening disorders: PKU formula, low-protein foods, metabolic supplements, testing supplies",
        ],
        relationship: "community on-ramp and revenue engine for Cureledger data infrastructure",
      },
      description: "Consumer product review platform and Shopify storefront by Cureledger, curated by rare disease communities. Covers both EDS products and newborn-screening-disorder products. Affiliate revenue transparently funds platform development. No venture capital, no data exploitation.",
    },
    "DataTrust": {
      id: "DataTrust",
      type: "legal_structure",
      name: "Cureledger Data Trust",
      properties: {
        structure: "bankruptcy-remote trust",
        ownership: "patient",
        custodian: "Cureledger Inc.",
        compliance: ["HIPAA", "GDPR"],
        features: ["conditional_reidentification", "data_portability", "withdrawal_rights"],
      },
      description: "Legal structure ensuring patient data sovereignty. Patients own data; Cureledger is custodian/trustee. Designed to prevent the 23andMe problem (where owned patient data went into bankruptcy proceedings).",
    },

    "PKU": {
      id: "PKU",
      type: "disorder",
      name: "Phenylketonuria",
      properties: {
        abbreviation: "PKU",
        category: "inborn_error_of_metabolism",
        prevalence: "1 in 10,000 to 15,000",
        inheritance: "autosomal recessive",
        gene: "PAH",
        screened_at_birth: true,
        rusp: true,
        known_since: "1960s",
      },
      description: "Metabolic disorder where phenylalanine cannot be properly metabolized. Screened at birth since 1960s. Treatment: dietary restriction + medical food (free amino acid formula). Adults still see pediatricians; no daily at-home monitoring exists.",
    },
    "EDS": {
      id: "EDS",
      type: "disorder_family",
      name: "Ehlers-Danlos Syndrome",
      properties: {
        subtypes: 13,
        most_common: "hEDS (hypermobile)",
        prevalence: "1 in 2,500 to 5,000 (varies by subtype)",
        inheritance: "varies (AD, AR)",
        comorbidities: ["POTS", "MCAS", "gastroparesis", "Chiari malformation"],
        screened_at_birth: false,
      },
      description: "Family of 13 connective tissue disorders affecting joints, skin, and blood vessels. Most common subtype (hEDS) has no identified gene. Average diagnostic odyssey: 10+ years.",
    },
    "Galactosemia": {
      id: "Galactosemia",
      type: "disorder",
      name: "Classic Galactosemia",
      properties: {
        abbreviation: "GALT",
        category: "inborn_error_of_metabolism",
        prevalence: "1 in 30,000 to 60,000",
        inheritance: "autosomal recessive",
        gene: "GALT",
        screened_at_birth: true,
        rusp: true,
      },
      description: "Inability to metabolize galactose. Requires immediate dietary intervention at birth. Screened via RUSP.",
    },
    "MSUD": {
      id: "MSUD",
      type: "disorder",
      name: "Maple Syrup Urine Disease",
      properties: {
        abbreviation: "MSUD",
        category: "inborn_error_of_metabolism",
        prevalence: "1 in 185,000 (general) to 1 in 380 (Old Order Mennonite)",
        inheritance: "autosomal recessive",
        screened_at_birth: true,
        rusp: true,
      },
      description: "Inability to metabolize branched-chain amino acids (leucine, isoleucine, valine). Named for sweet-smelling urine. Life-threatening without dietary management.",
    },

    "PlausibleMechanism": {
      id: "PlausibleMechanism",
      type: "regulatory_pathway",
      name: "Plausible Mechanism Framework",
      properties: {
        issuer: "FDA",
        status: "draft guidance",
        requirement: "well-characterized natural history data",
        significance: "enables individualized therapies without traditional RCTs",
      },
      description: "FDA draft guidance allowing drug approval for individualized therapies if a plausible mechanism and sufficient natural history data are demonstrated. Does not require traditional randomized controlled trials with thousands of patients.",
    },
    "CuresAct": {
      id: "CuresAct",
      type: "legislation",
      name: "21st Century Cures Act",
      properties: {
        enacted: 2016,
        significance: "formalized Real-World Evidence for regulatory submissions",
      },
      description: "Federal law that formalized Real-World Evidence (RWE) as a valid basis for FDA regulatory submissions, opening pathways for rare disease data.",
    },
    "ISTAND": {
      id: "ISTAND",
      type: "regulatory_pathway",
      name: "ISTAND Pilot",
      properties: {
        issuer: "FDA",
        purpose: "novel biomarker qualification",
      },
      description: "FDA pilot program establishing pathways for qualification of novel biomarkers, relevant to rare disease monitoring and N-of-1 data.",
    },
    "RUSP": {
      id: "RUSP",
      type: "screening_panel",
      name: "Recommended Uniform Screening Panel",
      properties: {
        conditions: "35+ core conditions",
        governance_historical: "ACHDNC (Advisory Committee on Heritable Disorders in Newborns and Children). Terminated April 2025.",
        mechanism: "heel-prick blood spot test",
        inventor: "Robert Guthrie (1963)",
      },
      description: "Federal panel of conditions screened in all US newborns. Robert Guthrie invented the heel-prick test in 1963 for PKU. That test became the foundation of newborn screening. Historically governed by ACHDNC, which was terminated in April 2025 leaving no federal advisory body for newborn screening.",
    },
    "ACHDNC": {
      id: "ACHDNC",
      type: "regulatory_body",
      name: "Advisory Committee on Heritable Disorders in Newborns and Children",
      properties: {
        abbreviation: "ACHDNC",
        status: "terminated",
        terminated: "April 2025",
        former_role: "federal advisory committee governing additions to the RUSP",
        impact: "no federal voice for newborn screening since termination",
      },
      description: "Federal advisory committee that governed which conditions were added to the Recommended Uniform Screening Panel. Terminated in April 2025, leaving no federal advisory body for newborn screening. This creates an advocacy vacuum that Cureledger's newborn screening vertical is positioned to help fill through content, data, and community organizing, not by claiming to replace a federal committee.",
    },
    "RobertGuthrie": {
      id: "RobertGuthrie",
      type: "person",
      name: "Robert Guthrie",
      properties: {
        born: 1916,
        died: 1995,
        role: "microbiologist",
        invention: "newborn screening heel-prick test (1963)",
        motivation: "nephew with intellectual disability from PKU",
      },
      description: "Microbiologist who invented the bacterial inhibition assay for PKU screening in 1963. His cheap, scalable test became the foundation of universal newborn screening. The Guthrie agent is named in his honor.",
    },
    "PlausibleMechanismComment": {
      id: "PlausibleMechanismComment",
      type: "regulatory_event",
      name: "FDA Plausible Mechanism Framework Public Comment",
      properties: {
        issuer: "FDA",
        document: "Plausible Mechanism Framework draft guidance",
        comment_deadline: "2026-04-27",
        submission_venue: "regulations.gov",
        time_sensitive: true,
      },
      description: "Public comment period on the FDA's Plausible Mechanism Framework draft guidance. Deadline: April 27, 2026. The framework is significant for rare disease because it contemplates approval of individualized therapies based on plausible mechanism plus well-characterized natural history data, rather than traditional large-cohort RCTs. NOTE: this entity is time-sensitive; after April 27, 2026, it becomes a historical reference rather than a live event.",
    },

    "NOf1": {
      id: "NOf1",
      type: "research_paradigm",
      name: "N-of-1 Research",
      properties: {
        principle: "dense longitudinal data from individual patients",
        scaling: {
          "1": "anecdote",
          "10": "case series",
          "50": "signal",
          "200": "natural history",
          "1000": "population model",
          "10000+": "engine of cures",
        },
        key_insight: "a single patient with daily structured data produces more data points in a year than most clinical trials collect from their entire cohort",
      },
      description: "Research paradigm where dense individual patient data replaces sparse large-cohort data. Modern causal inference and foundation models can extract signal that traditional statistics cannot. A disease with 200 known patients is not hopeless. It is under-instrumented.",
    },
  },

  relationships: [
    { from: "Cureledger", to: "ZebraReports", type: "operates" },
    { from: "Cureledger", to: "DataTrust", type: "governed_by" },
    { from: "RobertGuthrie", to: "RUSP", type: "invented" },
    { from: "RobertGuthrie", to: "Cureledger", type: "namesake_of_agent" },
    { from: "ACHDNC", to: "RUSP", type: "formerly_governed" },
    { from: "RUSP", to: "PKU", type: "screens_for" },
    { from: "RUSP", to: "Galactosemia", type: "screens_for" },
    { from: "RUSP", to: "MSUD", type: "screens_for" },
    { from: "PlausibleMechanism", to: "NOf1", type: "enables" },
    { from: "PlausibleMechanismComment", to: "PlausibleMechanism", type: "public_comment_period_for" },
    { from: "CuresAct", to: "PlausibleMechanism", type: "foundation_for" },
    { from: "ISTAND", to: "NOf1", type: "supports" },
    { from: "NOf1", to: "Cureledger", type: "core_paradigm_of" },
    { from: "DataTrust", to: "NOf1", type: "infrastructure_for" },
    { from: "ZebraReports", to: "EDS", type: "covers" },
    { from: "ZebraReports", to: "PKU", type: "covers" },
  ],

  facts: [
    "30 million Americans live with one of 7,000+ rare diseases",
    "95% of rare diseases have no FDA-approved treatment",
    "Drug development economics prioritize common conditions. Research and funding allocation follow disease prevalence, which structurally orphans rare disease patients.",
    "Even patients identified at birth through newborn screening are underserved. Treatments date back decades, adult care is rare, and at-home monitoring tools do not exist for most conditions.",
    "Cureledger's position is that rare disease is a data problem, not a science problem. When patient-generated data is structured and aggregated under patient control, cures become tractable.",
    "Cureledger was developed over more than a decade by a founder with a combined background in law, fintech development, and parenting a child with a rare disease. Design principle: human-centric, ethical, privacy-by-design.",
    "Average diagnostic odyssey for a rare disease patient is approximately 5 years",
    "Robert Guthrie invented the newborn screening heel-prick test in 1963 for PKU",
    "PKU has been known since the 1960s but treatment has barely changed. Adults still see pediatricians.",
    "PKU medical food (free amino acid formula) must be picked up at county health departments",
    "Most PKU patients never receive a genetic panel as part of diagnosis or treatment",
    "There is no daily at-home PKU monitor analogous to a diabetic glucose monitor",
    "EDS has 13 subtypes; the most common (hEDS) has no identified gene",
    "The FDA Plausible Mechanism Framework allows individualized therapy approval without traditional RCTs",
    "The 21st Century Cures Act formalized Real-World Evidence for regulatory submissions",
    "A single patient generating daily structured data produces more data points per year than most Phase 3 trials collect from their entire cohort",
    "Traditional Phase 3 trials collect approximately 50 data points per patient over months",
    "A patient logging daily structured data generates 2,000+ data points per year",
    "23andMe collected genetic data from millions, owned it, and that data may end up in bankruptcy proceedings",
    "Cureledger is structured as a data trust. Patients own their data. Cureledger Inc. is custodian and trustee.",
    "Disorders and their mechanisms constellate. Genetic variations reveal patterns only in aggregated data.",
    "When the mechanism is known and the data is structured, a cure is not a fantasy. It is an engineering problem.",
    "Drug development rewards chronic conditions at scale; rare disease falls outside that business model",
    "Zebra Reports affiliate revenue transparently funds platform development. No venture capital, no data exploitation.",
    "Making it to the newborn screening panel is a win for an inborn error of metabolism. Most of the 7,000+ disorders never get there.",
    "ACHDNC (Advisory Committee on Heritable Disorders in Newborns and Children) was terminated in April 2025. This is factual backstory about federal newborn screening governance, not Cureledger's core narrative.",
    "The FDA Plausible Mechanism Framework draft guidance has a public comment period ending April 27, 2026. Submissions go to regulations.gov.",
    "Zebra Reports covers both EDS products (braces, compression, mobility aids) and newborn-screening-disorder products (PKU formula, low-protein foods, metabolic supplements, testing supplies)",
    "Cureledger launches with two verticals from day one. EDS (community reach, affiliate revenue) and newborn screening (clinical seriousness, well-characterized natural history).",
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
