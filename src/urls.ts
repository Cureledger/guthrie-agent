/**
 * Absolute URLs for every user-facing link in Guthrie copy.
 * Relative paths break when pasted; models also hallucinate "#/..." — always use these.
 */
export const CURELEDGER_ORIGIN = "https://www.cureledger.com";

export const cureledgerUrl = {
  home: CURELEDGER_ORIGIN,
  /** Email signup / launch interest (hash section on marketing site) */
  emailSignup: `${CURELEDGER_ORIGIN}/#join`,
  blog: `${CURELEDGER_ORIGIN}/blog`,
  fdaComment: `${CURELEDGER_ORIGIN}/blog/fda-comment-plausible-mechanism-framework`,
  founderStory: `${CURELEDGER_ORIGIN}/blog/our-founder`,
  infrastructurePost: `${CURELEDGER_ORIGIN}/blog/the-fda-is-ready-the-infrastructure-is-not`,
  /** Read online (embeds PDF) */
  whitepaper: `${CURELEDGER_ORIGIN}/whitepaper`,
  /** Direct PDF (same document as the whitepaper page) */
  whitepaperPdf: `${CURELEDGER_ORIGIN}/cureledger-whitepaper-2026.pdf`,
  zebraReports: "https://zebrareports.com",
} as const;
