"""JobOS 4.0 — Job Statement Parsing and Linguistic Validation.

Axiom 5 from the Architectural Synthesis:
    "Job statement MUST start with an action verb. Forces the AI
    to maintain focus on action and execution rather than passive states."

Integrity Constraint C1 from the ontology design document:
    "Every Job.statement must start with a verb."
"""
from __future__ import annotations

import re
from dataclasses import dataclass


# ─── Action Verb Set ─────────────────────────────────────
# Curated set of action verbs valid as job statement openers.
# Matches the architectural document's requirement for imperative form.

ACTION_VERBS: frozenset[str] = frozenset({
    "achieve", "acquire", "adapt", "adopt", "align", "allocate", "analyze", "apply",
    "archive", "assess", "automate", "avoid", "accelerate",
    "build",
    "calculate", "capture", "change", "check", "clarify", "close", "conclude",
    "collaborate", "collect", "communicate", "compare", "complete",
    "conduct", "configure", "connect", "consolidate", "convert", "create", "customize",
    "adjust",
    "debug", "decide", "decrease", "define", "deliver", "deploy", "design",
    "detect", "develop", "diagnose", "discover", "distribute", "drive",
    "earn", "eliminate", "enable", "engage", "ensure", "establish", "evaluate",
    "execute", "expand", "experiment", "explore", "extract",
    "facilitate", "find", "fix", "forecast", "formulate",
    "generate", "grow",
    "handle",
    "identify", "implement", "improve", "increase", "inform", "innovate",
    "install", "integrate", "investigate",
    "launch", "learn", "leverage", "localize",
    "maintain", "manage", "map", "maximize", "measure", "migrate",
    "minimize", "mitigate", "monitor",
    "negotiate",
    "obtain", "onboard", "operate", "optimize", "orchestrate", "organize",
    "overcome",
    "perform", "pilot", "pivot", "plan", "predict", "prepare", "present", "prevent",
    "prioritize", "process", "produce", "protect", "provide", "publish",
    "qualify", "quantify",
    "reach", "recommend", "recruit", "reduce", "refine", "release", "remove", "replace",
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
})

_FIRST_WORD_RE = re.compile(r"^([a-zA-Z]+)\b")


# ─── Result Type ─────────────────────────────────────────

@dataclass
class ParsedJobStatement:
    """Parsed components of a job statement."""
    verb: str
    object: str
    context: str = ""
    raw: str = ""

    def to_string(self) -> str:
        parts = [self.verb, self.object]
        if self.context:
            parts.append(self.context)
        return " ".join(parts)


# ─── Public API ──────────────────────────────────────────

def validate_verb(statement: str) -> bool:
    """Check if a job statement starts with a valid action verb.

    Returns True if valid, False otherwise.
    """
    if not statement or not statement.strip():
        return False

    match = _FIRST_WORD_RE.match(statement.strip())
    if not match:
        return False

    first_word = match.group(1).lower()
    return first_word in ACTION_VERBS


def parse_job_statement(text: str) -> ParsedJobStatement:
    """Parse a job statement into verb + object + context.

    Handles formats:
        "verb object context"
        "verb object for actor when context"
        "verb object"

    Context markers: for, in, within, by, through, via, using,
                     when, where, while, during, before, after
    """
    text = text.strip()
    if not text:
        return ParsedJobStatement(verb="", object="", raw=text)

    # Extract first word as verb
    match = _FIRST_WORD_RE.match(text)
    if not match:
        return ParsedJobStatement(verb="", object=text, raw=text)

    verb = match.group(1).lower()
    rest = text[match.end():].strip()

    # Look for context markers
    context_markers = [
        " for ", " in ", " within ", " by ", " through ", " via ",
        " using ", " when ", " where ", " while ", " during ",
        " before ", " after ",
    ]

    split_pos = -1
    for marker in context_markers:
        pos = rest.lower().find(marker)
        if pos != -1 and (split_pos == -1 or pos < split_pos):
            split_pos = pos
            split_marker = marker

    if split_pos != -1:
        obj = rest[:split_pos].strip()
        context = rest[split_pos:].strip()
    else:
        obj = rest
        context = ""

    return ParsedJobStatement(
        verb=verb,
        object=obj,
        context=context,
        raw=text,
    )
