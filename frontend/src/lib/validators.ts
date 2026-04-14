/**
 * JobOS 4.0 — Job Statement Validators (TypeScript).
 *
 * Parity validators for Axiom 5 (Linguistic) running client-side.
 * Mirrors the Python logic in:
 *   - src/jobos/kernel/job_statement.py (ACTION_VERBS, validate_verb)
 *   - src/jobos/kernel/experience.py (validate_experiential_statement)
 *   - src/jobos/kernel/axioms.py (validate_linguistic_structure)
 *
 * These run in the browser before the API call to give instant feedback.
 * The authoritative validation still happens server-side (Python).
 */

// ─── Functional Job Verbs ────────────────────────────────
// Mirrors ACTION_VERBS from job_statement.py.
// Subset of most common verbs — server has the full set.

const FUNCTIONAL_VERBS: ReadonlySet<string> = new Set([
  "achieve", "acquire", "adapt", "adopt", "align", "analyze", "apply",
  "assess", "automate", "avoid",
  "build",
  "calculate", "capture", "change", "check", "clarify", "close",
  "collaborate", "collect", "communicate", "compare", "complete",
  "configure", "connect", "consolidate", "convert", "create", "customize",
  "debug", "decide", "decrease", "define", "deliver", "deploy", "design",
  "detect", "develop", "diagnose", "discover", "distribute", "drive",
  "eliminate", "enable", "engage", "ensure", "establish", "evaluate",
  "execute", "expand", "experiment", "explore", "extract",
  "facilitate", "find", "fix", "formulate",
  "generate", "grow",
  "handle",
  "identify", "implement", "improve", "increase", "inform", "innovate",
  "install", "integrate", "investigate",
  "launch", "learn", "leverage",
  "maintain", "manage", "map", "maximize", "measure", "migrate",
  "minimize", "mitigate", "monitor",
  "negotiate",
  "obtain", "onboard", "operate", "optimize", "orchestrate", "organize",
  "overcome",
  "perform", "pilot", "plan", "predict", "prepare", "present", "prevent",
  "prioritize", "process", "produce", "protect", "provide", "publish",
  "qualify", "quantify",
  "reach", "recommend", "recruit", "reduce", "refine", "remove", "replace",
  "report", "request", "research", "resolve", "restructure", "retain",
  "retire", "review", "revise", "run",
  "scale", "schedule", "secure", "select", "sell", "serve", "setup",
  "ship", "simplify", "solve", "source", "standardize", "start", "stop",
  "streamline", "strengthen", "structure", "submit", "support", "sustain",
  "synchronize",
  "target", "test", "track", "train", "transfer", "transform",
  "translate", "troubleshoot",
  "understand", "unify", "update", "upgrade",
  "validate", "verify", "visualize",
  "write",
]);

// Experiential statement opener regex (Axiom 5 — Dimension A).
// Matches "feel" or "to be" as complete words at string start.
// "feeling" does NOT match — word boundary enforced.
const EXPERIENTIAL_RE = /^(to\s+be\b|feel\b)/i;


// ─── Validators ──────────────────────────────────────────

/**
 * Validate a functional job statement starts with a known action verb.
 *
 * @param statement - The job statement to validate.
 * @returns true if the first word is a valid action verb.
 *
 * @example
 * validateFunctionalJobStatement("Define success criteria")  // true
 * validateFunctionalJobStatement("Success is defined by")    // false
 */
export function validateFunctionalJobStatement(statement: string): boolean {
  if (!statement || !statement.trim()) return false;
  const firstWord = statement.trim().split(/\s+/)[0].toLowerCase();
  return FUNCTIONAL_VERBS.has(firstWord);
}

/**
 * Validate an experiential job statement (Dimension A — Experience Space).
 *
 * Statement must start with "To Be" or "Feel" (case-insensitive).
 *
 * @param statement - The experiential statement to validate.
 * @returns true if the statement starts with a valid experiential prefix.
 *
 * @example
 * validateExperientialStatement("To Be seen as a trusted advisor")  // true
 * validateExperientialStatement("Feel confident in delivery")        // true
 * validateExperientialStatement("feel connected to the team")        // true
 * validateExperientialStatement("Define confidence metrics")         // false
 */
export function validateExperientialStatement(statement: string): boolean {
  if (!statement || !statement.trim()) return false;
  return EXPERIENTIAL_RE.test(statement.trim());
}

/**
 * Unified job statement validator.
 *
 * Routes to functional or experiential validation based on the isExperiential flag.
 *
 * @param statement     - The job statement to validate.
 * @param isExperiential - True for T4 Experience jobs; false (default) for T1–T3.
 * @returns true if the statement is valid for its type.
 */
export function validateJobStatement(
  statement: string,
  isExperiential = false,
): boolean {
  return isExperiential
    ? validateExperientialStatement(statement)
    : validateFunctionalJobStatement(statement);
}

/**
 * Get the first word (potential verb) from a job statement.
 * Useful for error messages in the UI.
 */
export function extractFirstWord(statement: string): string {
  if (!statement || !statement.trim()) return "";
  return statement.trim().split(/\s+/)[0];
}
