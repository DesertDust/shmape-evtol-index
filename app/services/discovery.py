from dataclasses import dataclass
import re


@dataclass(frozen=True)
class DiscoveryCandidate:
    name: str
    ticker: str
    exchange: str
    is_public: bool
    description: str
    evidence_urls: tuple[str, ...] = ()


@dataclass(frozen=True)
class DiscoveryDecision:
    score: int
    auto_include: bool
    reasons: tuple[str, ...]


_MATERIAL_PATTERNS = (
    r"electric vertical takeoff",
    r"electric vertical take-off",
    r"\bevtol\b",
    r"advanced air mobility",
    r"urban air mobility",
    r"air taxi",
)
_WEAK_PATTERNS = (r"investment", r"minority stake", r"experimental", r"portfolio company")
_STRONG_MATERIALITY = (
    r"develops? (and certifies? )?.{0,40}(electric vertical|evtol)",
    r"manufactures? .{0,40}(electric vertical|evtol)",
    r"operates? .{0,40}(air taxi|evtol|air mobility platform)",
)


def score_candidate(candidate: DiscoveryCandidate) -> DiscoveryDecision:
    text = f"{candidate.name} {candidate.description}".lower()
    reasons = []
    score = 0
    if candidate.is_public and candidate.ticker and candidate.exchange:
        score += 35
        reasons.append("public listing")
    else:
        reasons.append("not a verified public listing")
    material_hits = sum(bool(re.search(pattern, text)) for pattern in _MATERIAL_PATTERNS)
    if material_hits:
        score += min(45, 25 + 10 * material_hits)
        reasons.append("material eVTOL activity")
    if any(re.search(pattern, text) for pattern in _STRONG_MATERIALITY):
        score += 10
        reasons.append("eVTOL is described as an operating business")
    if len(candidate.evidence_urls) >= 2:
        score += 15
        reasons.append("multiple evidence sources")
    elif candidate.evidence_urls:
        score += 5
        reasons.append("single evidence source")
    if any(re.search(pattern, text) for pattern in _WEAK_PATTERNS):
        score -= 20
        reasons.append("eVTOL appears non-material")
    score = max(0, min(100, score))
    has_operating_language = "eVTOL is described as an operating business" in reasons
    return DiscoveryDecision(score, candidate.is_public and score >= 90 and has_operating_language, tuple(reasons))
