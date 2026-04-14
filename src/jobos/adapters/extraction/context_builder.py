"""Build structured 5W1H context from raw text using LLM."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ContextSummary:
    who: str = ""
    why: str = ""
    what: str = ""
    where: str = ""
    when: str = ""
    how: str = ""
    keywords: list[str] = field(default_factory=list)
    job_hints: list[str] = field(default_factory=list)


async def build_context_from_text(
    text: str,
    llm: object | None = None,
) -> ContextSummary:
    """Use LLM to extract structured 5W1H context from raw text.

    Falls back to keyword extraction when LLM is unavailable.
    """
    if llm is not None and hasattr(llm, "complete_json"):
        try:
            return await _llm_extract(text, llm)
        except Exception as e:
            logger.warning("LLM context extraction failed, using fallback: %s", e)

    return _fallback_extract(text)


async def _llm_extract(text: str, llm: object) -> ContextSummary:
    """LLM-powered 5W1H extraction."""
    # Truncate to avoid exceeding token limits
    truncated = text[:4000] if len(text) > 4000 else text

    system_prompt = (
        "You are a structured data extraction engine. "
        "Extract 5W1H context and job hints from the given text. "
        "Respond in valid JSON only."
    )

    user_prompt = f"""Analyze this text and extract structured context.

Text:
{truncated}

Respond in this exact JSON format:
{{
  "who": "Who is the actor or stakeholder?",
  "why": "Why is this being done? What is the motivation?",
  "what": "What is the core task or objective?",
  "where": "Where does this take place (domain, context)?",
  "when": "When or under what conditions?",
  "how": "How is this accomplished or approached?",
  "keywords": ["keyword1", "keyword2", "keyword3"],
  "job_hints": ["Verb + object job statement 1", "Verb + object job statement 2"]
}}

For job_hints, write them as Jobs-to-be-Done statements starting with action verbs.
If a field is unclear from the text, use an empty string."""

    parsed = await llm.complete_json(system_prompt, user_prompt, max_tokens=600)  # type: ignore[union-attr]

    return ContextSummary(
        who=parsed.get("who", ""),
        why=parsed.get("why", ""),
        what=parsed.get("what", ""),
        where=parsed.get("where", ""),
        when=parsed.get("when", ""),
        how=parsed.get("how", ""),
        keywords=parsed.get("keywords", []),
        job_hints=parsed.get("job_hints", []),
    )


def _fallback_extract(text: str) -> ContextSummary:
    """Simple keyword extraction without LLM."""
    words = text.split()
    # Extract simple keywords: words > 4 chars, deduplicated, top 10
    seen: set[str] = set()
    keywords: list[str] = []
    for w in words:
        clean = w.strip(".,;:!?()[]{}\"'").lower()
        if len(clean) > 4 and clean.isalpha() and clean not in seen:
            seen.add(clean)
            keywords.append(clean)
            if len(keywords) >= 10:
                break

    return ContextSummary(
        what=text[:200] if text else "",
        keywords=keywords,
    )
