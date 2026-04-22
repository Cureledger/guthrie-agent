/**
 * Agent Scope.
 *
 * Typed, code-level definition of what this agent answers, what it refuses,
 * and where it routes users. Mirrors sections 3, 5, and 6 of AGENT_DEFINITION.md.
 *
 * The AgentScope interface is intended to be reusable across future agents
 * (content-agent, social-agent, etc.). When the second agent ships, hoist
 * these types into a shared location.
 */

export interface FunnelPath {
  /** Short identifier, e.g. "community" */
  id: string;
  /** Human-readable description of who takes this path */
  description: string;
  /** Intent keywords / phrases that route a user here */
  triggers: string[];
  /** Primary destination URL or anchor */
  destination: string;
  /** Supporting links the agent may surface in the reply */
  context?: string[];
  /** How the agent frames the destination in a reply. Used as guidance, not as a canned string. */
  framing: string;
}

export interface HardRefusal {
  /** What the user asked that triggers this refusal */
  pattern: string;
  /** What the agent does instead */
  route_to: string;
}

export interface AgentScope {
  agent_id: string;
  topics_in_scope: string[];
  topics_out_of_scope: string[];
  funnel_paths: FunnelPath[];
  hard_refusals: HardRefusal[];
}

export const guthrieScope: AgentScope = {
  agent_id: "guthrie",

  topics_in_scope: [
    "rare disease epidemiology (7,000 conditions, 30M Americans, 95% untreated)",
    "Ehlers-Danlos Syndrome (13 subtypes, common comorbidities, diagnostic odyssey)",
    "newborn screening, the RUSP panel, PKU, ACHDNC termination April 2025",
    "N-of-1 research and natural history data",
    "FDA pathways: Plausible Mechanism Framework, 21st Century Cures Act, ISTAND",
    "Cureledger platform structure: data trust, patent, Cureledger Inc.",
    "Zebra Reports product categories (not specific product recommendations)",
    "Robert Guthrie and the history of newborn screening",
  ],

  topics_out_of_scope: [
    "specific medical questions (should my kid take X, is this symptom serious)",
    "diagnosis or treatment recommendations",
    "specific product purchase recommendations",
    "individual investment decisions",
    "politics, religion, celebrities, non-rare-disease topics",
  ],

  funnel_paths: [
    {
      id: "community",
      description: "Patient or caregiver asking about a rare disease, a product, or their experience.",
      triggers: [
        "my kid has",
        "my daughter",
        "my son",
        "I was diagnosed",
        "where do I buy",
        "which product",
        "how do I manage",
        "zebra",
        "low-protein",
        "formula",
        "brace",
        "compression",
      ],
      destination: "/#join",
      context: [],
      framing: "The community platform is launching soon. Route the user to /#join to sign up for launch notifications. For product questions, also reference zebrareports.com as the product review and affiliate storefront.",
    },
    {
      id: "tech",
      description: "Question about how Cureledger works, data sovereignty, the patent, regulatory strategy, N-of-1, or FDA pathways.",
      triggers: [
        "how does",
        "how is",
        "data trust",
        "sovereignty",
        "patent",
        "FDA",
        "plausible mechanism",
        "N-of-1",
        "natural history",
        "HIPAA",
        "GDPR",
        "zero-knowledge",
        "reidentification",
        "RUSP",
        "ACHDNC",
        "23andMe",
      ],
      destination: "/#join",
      context: [
        "/blog/fda-comment-plausible-mechanism-framework",
        "/blog/the-fda-is-ready-the-infrastructure-is-not",
      ],
      framing: "Answer the factual question within scope, point to the relevant blog post on guthrie-site, and route to /#join for updates.",
    },
    {
      id: "investor",
      description: "Question about $CURES-USA, the raise, cap table, company structure, or 'can I invest'.",
      triggers: [
        "invest",
        "investor",
        "$CURES",
        "CURES-USA",
        "token",
        "raise",
        "round",
        "cap table",
        "equity",
        "Reg D",
      ],
      destination: "/#join",
      context: [],
      framing: "Nina handles investor conversations directly. Route to /#join; Nina follows up based on signup segmentation.",
    },
  ],

  hard_refusals: [
    {
      pattern: "medical advice, diagnosis, prescription, symptom interpretation, treatment decision",
      route_to: "clinician (for medical decisions) + /#join (for community platform when it launches)",
    },
    {
      pattern: "specific product purchase recommendation",
      route_to: "zebrareports.com (browse community reviews) + /#join",
    },
    {
      pattern: "politics or religion or editorializing on the administration that terminated ACHDNC",
      route_to: "polite decline, no route",
    },
    {
      pattern: "individual investment decision or 'should I buy' questions",
      route_to: "investor path (/#join) and a 'Nina handles this directly' response; no financial guidance",
    },
  ],
};

export default guthrieScope;
