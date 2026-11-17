import re
from collections import Counter
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Set, Tuple

from backend.schemas import (
    AnalysisContext,
    BulletDeterministicAudit,
    DeterministicCVAudit,
    EvidenceTier,
    ExtractedBullet,
    ExtractedCV,
    ScoreDeductionItem,
    SkillsCredibilityAudit,
)


WEAK_OPENING_PATTERNS: List[Tuple[str, re.Pattern]] = [
    ("Responsible for", re.compile(r"^responsible\s+for\b", re.I)),
    ("Worked on", re.compile(r"^worked\s+(?:on|with)\b", re.I)),
    ("Helped / Assisted with", re.compile(r"^(?:helped|assisted)\s+(?:with|in|to|the)?\b", re.I)),
    ("Duties included", re.compile(r"^(?:duties|responsibilities)\s+included\b", re.I)),
    ("Involved in", re.compile(r"^(?:was\s+)?involved\s+in\b", re.I)),
    ("Tasked with", re.compile(r"^(?:was\s+)?tasked\s+with\b", re.I)),
    ("Participated in", re.compile(r"^participated\s+in\b", re.I)),
    ("Contributed to", re.compile(r"^contributed\s+to\b", re.I)),
    ("Used / Utilised", re.compile(r"^(?:used|utili[sz]ed)\b", re.I)),
]

BUZZWORDS_LIST: List[str] = [
    "hard-working",
    "hardworking",
    "passionate",
    "results-driven",
    "results driven",
    "detail-oriented",
    "detail oriented",
    "team player",
    "dynamic",
    "synergy",
    "go-getter",
    "thought leader",
    "rockstar",
    "ninja",
    "guru",
    "self-starter",
    "motivated individual",
    "fast learner",
    "quick learner",
    "proven track record",
    "world-class",
    "visionary",
    "cutting-edge",
    "best-in-class",
]

STRONG_ACTION_VERBS: Set[str] = {
    "architected",
    "built",
    "designed",
    "developed",
    "engineered",
    "implemented",
    "refactored",
    "optimised",
    "optimized",
    "migrated",
    "automated",
    "deployed",
    "reduced",
    "increased",
    "accelerated",
    "resolved",
    "diagnosed",
    "spearheaded",
    "led",
    "authored",
    "integrated",
    "constructed",
    "benchmarked",
    "verified",
    "validated",
    "profiled",
    "consolidated",
    "streamlined",
    "delivered",
    "launched",
    "established",
    "negotiated",
    "analysed",
    "analyzed",
    "modelled",
    "modeled",
    "orchestrated",
    "provisioned",
    "containerised",
    "containerized",
    "secured",
}

from backend.it_vocabulary import (  # noqa: E402
    BASELINE_REGEX,
    CANONICAL_SKILLS,
    GENERIC_MECHANISM_REGEX,
    IT_METHOD_REGEX,
    METRIC_OR_SCOPE_REGEX,
    OUTCOME_SIGNAL_REGEX,
    SOFTWARE_METHOD_REGEX,
)

UNANCHORED_CLAIM_PATTERNS: List[Tuple[str, re.Pattern]] = [
    (
        "Unanchored percentage claim without baseline, timeframe, or mechanism",
        re.compile(
            r"\b(?:improved|increased|boosted|reduced|cut|accelerated|enhanced|grew|optimised|optimized)\s+(?:[a-z]+\s+){0,3}by\s+\d{1,3}%",
            re.I,
        ),
    ),
    (
        "Implausible absolute perfection claim ('100% bug-free' / 'zero bugs' / '100% accuracy')",
        re.compile(r"\b(?:100%\s*(?:bug[\s-]?free|error[\s-]?free|uptime|accurate|accuracy)|zero\s+(?:bugs|defects|errors|downtime\s+ever))\b", re.I),
    ),
    (
        "Unsubstantiated hyper-scale or sole-ownership hyperbole",
        re.compile(r"\b(?:single[\s-]?handedly\s+(?:built|architected|transformed|saved)|expert\s+in\s+all|mastered\s+every|revolutioni[sz]ed\s+the\s+entire)\b", re.I),
    ),
]


def _n(count: int, singular: str, plural: str = "") -> str:
    return f"{count} {singular if count == 1 else plural or singular + 's'}"


def classify_bullet_evidence_tier(
    text: str,
) -> Tuple[EvidenceTier, str, str, bool, bool, bool, Optional[str], List[str], Optional[str]]:
    """
    Classify a single CV bullet or statement into one of the 5 explicit rubric evidence tiers:
    - tier_0_generic: Empty platitude, buzzword cluster, or generic claim with no concrete activity.
    - tier_1_responsibility_only: States a duty or task without a method, scale, or outcome.
    - tier_2_technical_detail: States what was done with a specific method, tool or technique, but lacks a concrete outcome.
    - tier_3_concrete_evidence: Provides a specific method and concrete scope or a verified qualitative result.
    - tier_4_verified_outcome: Provides a specific action, the method used, and a credible, contextualised measurable outcome.

    "Method" is field-neutral: software techniques, named professional methods (law, science, finance, engineering,
    healthcare, teaching, consulting), canonical skills, or an explicit "using/via/by doing" mechanism all count.
    """
    clean = text.strip()
    words = clean.split()
    word_count = len(words)
    low = clean.lower()

    buzzwords_found = [bw for bw in BUZZWORDS_LIST if bw in low]

    weak_prefix: Optional[str] = None
    for label, pat in WEAK_OPENING_PATTERNS:
        if pat.search(clean):
            weak_prefix = label
            break

    has_tech = (
        bool(SOFTWARE_METHOD_REGEX.search(clean))
        or bool(IT_METHOD_REGEX.search(clean))
        or bool(GENERIC_MECHANISM_REGEX.search(clean))
        or any(pat.search(clean) for _, pat in CANONICAL_SKILLS.values())
    )
    has_metric = bool(METRIC_OR_SCOPE_REGEX.search(clean))
    has_outcome_verb = bool(OUTCOME_SIGNAL_REGEX.search(clean))
    has_baseline_comparison = bool(BASELINE_REGEX.search(clean))

    has_unanchored = False
    unanchored_reason: Optional[str] = None
    for reason, pat in UNANCHORED_CLAIM_PATTERNS:
        if pat.search(clean):
            # If it's a percentage claim, check whether it has a baseline ("from X to Y") or concrete method ("by implementing/via/using")
            if "percentage claim" in reason and (has_baseline_comparison or (has_tech and word_count >= 16)):
                continue
            has_unanchored = True
            unanchored_reason = reason
            break

    # Also flag vague improvement claims with no metric and no method
    if not has_unanchored and re.search(
        r"\b(?:improved\s+performance|increased\s+efficiency|made\s+it\s+faster|optimised\s+the\s+system|many\s+users)\b",
        clean,
        re.I,
    ) and not has_metric and not has_baseline_comparison:
        has_unanchored = True
        unanchored_reason = "Vague outcome claim ('improved performance' / 'increased efficiency') without a measurement or the method used"

    # Determine Evidence Tier
    if (buzzwords_found and word_count < 18 and not has_tech) or word_count < 5:
        tier: EvidenceTier = "tier_0_generic"
        label = "Tier 0 — Generic / Unsubstantiated Platitude"
        reason = "Contains generic self-praise or fragment without concrete task, methodology, or verifiable evidence."
    elif has_unanchored and not has_tech:
        tier = "tier_1_responsibility_only"
        label = "Tier 1 — Activity Mentioned with Unverified Claim"
        reason = unanchored_reason or "Mentions an activity with an unsubstantiated claim but no method or evidence."
    elif (has_tech or has_baseline_comparison) and has_metric and (has_outcome_verb or has_baseline_comparison) and not has_unanchored:
        tier = "tier_4_verified_outcome"
        label = "Tier 4 — Credible Outcome with Concrete Evidence & Mechanism"
        reason = "Demonstrates what was done or changed, the method or the measured change, and a contextualised, credible result."
    elif has_tech and (has_outcome_verb or has_metric) and word_count >= 12 and not has_unanchored:
        tier = "tier_3_concrete_evidence"
        label = "Tier 3 — Contribution Supported by Concrete Evidence"
        reason = "Substantiates contribution with a specific method and the scope or outcome of the work."
    elif has_tech and word_count >= 9:
        tier = "tier_2_technical_detail"
        label = "Tier 2 — Responsibility Described with Method Detail"
        reason = "Names the specific method, tool or technique used, but stops short of proving the resulting impact or scale."
    else:
        tier = "tier_1_responsibility_only"
        label = "Tier 1 — Responsibility / Task Mentioned Only"
        reason = "Describes routine duties or participation without explaining the method, individual ownership, or outcome."

    return (
        tier,
        label,
        reason,
        has_tech,
        has_metric,
        has_unanchored,
        unanchored_reason,
        buzzwords_found,
        weak_prefix,
    )


def run_deterministic_cv_audit(extracted_cv: ExtractedCV) -> DeterministicCVAudit:
    """
    Execute all deterministic document, linguistic, repetition, duplication, and evidence-tier checks
    on the parsed CV.
    """
    bullet_audits: List[BulletDeterministicAudit] = []
    tier_counts: Dict[str, int] = {
        "tier_0_generic": 0,
        "tier_1_responsibility_only": 0,
        "tier_2_technical_detail": 0,
        "tier_3_concrete_evidence": 0,
        "tier_4_verified_outcome": 0,
    }
    opening_verb_counter: Counter = Counter()
    all_buzzwords: Set[str] = set()
    unanchored_claims: List[Dict[str, str]] = []
    short_count = 0
    overlong_count = 0
    total_bullet_words = 0

    # Evaluate experience, project, and summary items
    evaluatable_items: List[ExtractedBullet] = []
    for sec in extracted_cv.sections:
        if sec.normalized_type in ("experience", "projects", "summary", "additional"):
            for item in sec.items:
                # Skip entry headers (e.g., "Software Engineer | Acme | 2022 - Present")
                if not item.is_bullet and sec.normalized_type in ("experience", "projects"):
                    continue
                evaluatable_items.append(item)

    for item in evaluatable_items:
        txt = item.text.strip()
        words = txt.split()
        wc = len(words)
        total_bullet_words += wc
        sentences = [s.strip() for s in re.split(r"[.!?]+", txt) if s.strip()]
        sc = max(1, len(sentences))

        first_word = re.sub(r"[^a-zA-Z-]", "", words[0]).lower() if words else ""
        if first_word and len(first_word) > 2:
            opening_verb_counter[first_word] += 1

        (
            tier,
            tier_label,
            tier_reason,
            has_tech,
            has_metric,
            has_unanchored,
            unanchored_reason,
            buzzwords,
            weak_prefix,
        ) = classify_bullet_evidence_tier(txt)

        tier_counts[tier] = tier_counts.get(tier, 0) + 1
        for bw in buzzwords:
            all_buzzwords.add(bw)

        if has_unanchored and unanchored_reason:
            unanchored_claims.append(
                {
                    "bullet_id": item.bullet_id,
                    "section": item.section_name,
                    "text": txt,
                    "reason": unanchored_reason,
                }
            )

        is_short = wc < 8
        is_long = wc > 38
        if is_short:
            short_count += 1
        if is_long:
            overlong_count += 1

        bullet_audits.append(
            BulletDeterministicAudit(
                bullet_id=item.bullet_id,
                section_name=item.section_name,
                entry_title=item.entry_title,
                text=txt,
                word_count=wc,
                sentence_count=sc,
                opening_word=first_word,
                evidence_tier=tier,
                evidence_tier_label=tier_label,
                evidence_tier_reason=tier_reason,
                has_concrete_tech_or_method=has_tech,
                has_verified_metric_or_scope=has_metric,
                has_unanchored_claim=has_unanchored,
                unanchored_claim_reason=unanchored_reason,
                buzzwords_found=buzzwords,
                weak_verb_prefix=weak_prefix,
                is_too_short=is_short,
                is_overlong=is_long,
            )
        )

    # Detect duplicate or near-duplicate bullets across the CV
    duplicate_pairs: List[Dict[str, str]] = []
    for i in range(len(bullet_audits)):
        for j in range(i + 1, len(bullet_audits)):
            a = bullet_audits[i]
            b = bullet_audits[j]
            norm_a = " ".join(a.text.lower().split())
            norm_b = " ".join(b.text.lower().split())
            if len(norm_a) < 15 or len(norm_b) < 15:
                continue
            sim = SequenceMatcher(None, norm_a, norm_b).ratio()
            if sim >= 0.76:
                b.duplicate_of_bullet_id = a.bullet_id
                duplicate_pairs.append(
                    {
                        "first_bullet_id": a.bullet_id,
                        "second_bullet_id": b.bullet_id,
                        "first_section": a.section_name,
                        "second_section": b.section_name,
                        "first_text": a.text,
                        "second_text": b.text,
                        "similarity": f"{int(round(sim * 100))}%",
                    }
                )

    # Detect repeated opening words (used >= 3 times)
    repeated_verbs = {
        verb: count for verb, count in opening_verb_counter.items() if count >= 3
    }

    # Detect repeated 3-word phrases across bullets
    ngram_counts: Counter = Counter()
    stopwords = {"the", "and", "for", "with", "that", "from", "into", "across", "using", "worked", "responsible"}
    for ba in bullet_audits:
        tokens = [re.sub(r"[^a-z0-9]", "", w.lower()) for w in ba.text.split()]
        tokens = [t for t in tokens if len(t) > 2]
        seen_in_bullet = set()
        for k in range(len(tokens) - 2):
            tri = f"{tokens[k]} {tokens[k+1]} {tokens[k+2]}"
            if all(t in stopwords for t in (tokens[k], tokens[k+1], tokens[k+2])):
                continue
            seen_in_bullet.add(tri)
        for tri in seen_in_bullet:
            ngram_counts[tri] += 1

    repeated_phrases = [phrase for phrase, c in ngram_counts.most_common(6) if c >= 3]

    # Also scan full text for any buzzwords in summary/skills that weren't in bullets
    raw_low = extracted_cv.raw_text.lower()
    for bw in BUZZWORDS_LIST:
        if bw in raw_low:
            all_buzzwords.add(bw)

    avg_words = round(total_bullet_words / max(1, len(bullet_audits)), 1) if bullet_audits else 0.0

    audit = DeterministicCVAudit(
        total_words=extracted_cv.diagnostics.word_count,
        total_bullets=len(bullet_audits),
        avg_bullet_words=avg_words,
        short_bullets_count=short_count,
        overlong_bullets_count=overlong_count,
        tier_counts=tier_counts,
        repeated_opening_verbs=repeated_verbs,
        duplicate_bullet_pairs=duplicate_pairs,
        repeated_phrases=repeated_phrases,
        buzzwords_detected=sorted(all_buzzwords),
        unanchored_claims_detected=unanchored_claims,
        bullet_audits=bullet_audits,
    )
    extracted_cv.deterministic_audit = audit
    return audit


def run_skills_credibility_audit(extracted_cv: ExtractedCV) -> SkillsCredibilityAudit:
    """
    Deterministically cross-reference skills claimed in the Skills section against
    actual evidence in Experience and Projects sections.
    """
    skills_sections = [s for s in extracted_cv.sections if s.normalized_type == "skills"]
    evidence_sections = [
        s for s in extracted_cv.sections if s.normalized_type in ("experience", "projects", "certifications")
    ]

    skills_text = "\n".join(line for s in skills_sections for line in s.raw_lines)
    evidence_lines = [
        (s.title, item.text)
        for s in evidence_sections
        for item in s.items
        if item.text.strip()
    ]
    evidence_blob = "\n".join(txt for _, txt in evidence_lines)

    claimed_skills: List[str] = []
    evidenced_skills: List[Dict[str, str]] = []
    unsupported_skills: List[str] = []
    omitted_demonstrated_skills: List[str] = []
    recommended_categories: Dict[str, List[str]] = {}

    # 1. Check canonical skills in skills section vs evidence sections
    for skill_name, (category, pattern) in CANONICAL_SKILLS.items():
        in_skills_sec = bool(pattern.search(skills_text)) if skills_text else False
        matching_evidence = [
            f"[{sec_title}] {line}"
            for sec_title, line in evidence_lines
            if pattern.search(line)
        ]

        if in_skills_sec:
            claimed_skills.append(skill_name)
            if matching_evidence:
                evidenced_skills.append(
                    {
                        "skill": skill_name,
                        "evidence": matching_evidence[0][:160],
                    }
                )
                recommended_categories.setdefault(category, []).append(skill_name)
            else:
                unsupported_skills.append(skill_name)
        elif matching_evidence:
            # Demonstrated in Experience/Projects, but omitted from Skills section (or no Skills section exists)
            omitted_demonstrated_skills.append(skill_name)
            evidenced_skills.append(
                {
                    "skill": skill_name,
                    "evidence": matching_evidence[0][:160],
                }
            )
            recommended_categories.setdefault(category, []).append(skill_name)

    # 2. Parse raw comma/pipe-separated tokens in the Skills section to catch non-canonical claimed tools
    if skills_text:
        for line in skills_text.splitlines():
            # Strip category prefix like "Languages:"
            cleaned_line = re.sub(r"^[A-Za-z\s/&]+:\s*", "", line).strip()
            tokens = [t.strip(" •●▪-*().") for t in re.split(r"[,|•;/]", cleaned_line) if t.strip()]
            for tok in tokens:
                if len(tok) < 2 or len(tok) > 28:
                    continue
                # Skip proficiency words
                if re.search(r"\b(?:expert|advanced|intermediate|beginner|proficient|fluent|years|100%)\b", tok, re.I):
                    continue
                already_matched = any(
                    tok.lower() == c.lower() or pat.search(tok)
                    for c, (_, pat) in CANONICAL_SKILLS.items()
                )
                if not already_matched and tok not in claimed_skills:
                    claimed_skills.append(tok)
                    if re.search(r"\b" + re.escape(tok) + r"\b", evidence_blob, re.I):
                        evidenced_skills.append(
                            {
                                "skill": tok,
                                "evidence": "Referenced in experience/project descriptions.",
                            }
                        )
                        recommended_categories.setdefault("Domain & Additional Tools", []).append(tok)
                    else:
                        unsupported_skills.append(tok)

    # 3. Check for unsubstantiated skill-level claims or overload
    overloaded_notes: List[str] = []
    if len(claimed_skills) > 20:
        overloaded_notes.append(
            f"Skills section lists {len(claimed_skills)} items. Listing more than 15–20 technologies dilutes your core specialism and signals indiscriminate keyword dumping."
        )
    if re.search(r"\b(?:expert|mastery|100%|95%|90%|5/5|\*\*\*\*\*)\b", skills_text, re.I):
        overloaded_notes.append(
            "Skills section contains self-assessed proficiency ratings (e.g., 'Expert', percentages, or star ratings) without objective calibration."
        )
    if len(unsupported_skills) > 0:
        overloaded_notes.append(
            f"{len(unsupported_skills)} of {_n(max(1, len(claimed_skills)), 'listed skill')} ({', '.join(unsupported_skills[:8])}) {'has' if len(unsupported_skills) == 1 else 'have'} no supporting evidence anywhere in your Work Experience or Projects."
        )

    if not skills_sections:
        commentary = (
            f"No dedicated Skills section was found. However, {len(omitted_demonstrated_skills)} technical/professional "
            f"skills ({', '.join(omitted_demonstrated_skills[:8])}) are evidenced in your work/project descriptions and should be structured into a concise Skills section."
        )
    elif len(unsupported_skills) > len(evidenced_skills):
        commentary = (
            f"Sceptical recruiter alert: {len(unsupported_skills)} out of {len(claimed_skills)} listed skills are completely unsubstantiated "
            "by your experience or project bullets. Listing a technology in a skills dump does not prove competence; either cite where you used each tool or cut it."
        )
    elif unsupported_skills:
        commentary = (
            f"{_n(len(evidenced_skills), 'skill')} {'is' if len(evidenced_skills) == 1 else 'are'} backed by concrete project or work evidence, but "
            f"{_n(len(unsupported_skills), 'listed skill')} ({', '.join(unsupported_skills[:6])}) never {'appears' if len(unsupported_skills) == 1 else 'appear'} in your work history. "
            f"Either anchor {'it' if len(unsupported_skills) == 1 else 'them'} to real deliverables or remove {'it' if len(unsupported_skills) == 1 else 'them'}."
        )
    else:
        commentary = (
            f"Strong skill hygiene: all {len(claimed_skills)} claimed skills are substantiated by concrete evidence inside your Experience or Projects sections."
        )

    return SkillsCredibilityAudit(
        claimed_skills=claimed_skills,
        evidenced_skills=evidenced_skills,
        unsupported_skills=unsupported_skills,
        omitted_demonstrated_skills=omitted_demonstrated_skills,
        overloaded_or_unsubstantiated_levels=overloaded_notes,
        recommended_categories=recommended_categories,
        recruiter_commentary=commentary,
    )


def compute_deterministic_category_baselines(
    extracted_cv: ExtractedCV,
    det_audit: DeterministicCVAudit,
    skills_audit: SkillsCredibilityAudit,
    context: AnalysisContext,
    role_fit: Optional[dict] = None,
    jd_alignment: Optional[int] = None,
) -> Tuple[
    Dict[str, int],
    Dict[str, List[ScoreDeductionItem]],
    Dict[str, List[str]],
    Dict[str, List[str]],
    Dict[str, List[str]],
    Dict[str, str],
]:
    """
    Calculate deterministic baseline scores (0-100) and auditable ScoreDeductionItem lists
    for each of the 7 rubric categories.
    Enforces strict non-overlapping penalty rules so the same defect is not double-penalised
    across categories without explicit justification.
    """
    scores: Dict[str, int] = {}
    deductions: Dict[str, List[ScoreDeductionItem]] = {k: [] for k in (
        "relevance_alignment",
        "impact_achievements",
        "experience_project_quality",
        "skills_credibility",
        "writing_clarity",
        "structure_readability",
        "ats_compatibility",
    )}
    evidence_map: Dict[str, List[str]] = {k: [] for k in deductions}
    weaknesses_map: Dict[str, List[str]] = {k: [] for k in deductions}
    improvements_map: Dict[str, List[str]] = {k: [] for k in deductions}
    uncertainty_map: Dict[str, str] = {}

    sec_types = [s.normalized_type for s in extracted_cv.sections]
    total_b = max(1, det_audit.total_bullets)
    t0 = det_audit.tier_counts.get("tier_0_generic", 0)
    t1 = det_audit.tier_counts.get("tier_1_responsibility_only", 0)
    t2 = det_audit.tier_counts.get("tier_2_technical_detail", 0)
    t3 = det_audit.tier_counts.get("tier_3_concrete_evidence", 0)
    t4 = det_audit.tier_counts.get("tier_4_verified_outcome", 0)

    # -------------------------------------------------------------------------
    # 1. IMPACT & ACHIEVEMENTS (Primary owner of Evidence Tiers 3 & 4 vs Tier 1 & unanchored metrics)
    # -------------------------------------------------------------------------
    impact_score = 50
    weak_duty_ratio = (t0 + t1) / total_b

    if t4 > 0:
        pts = min(35, t4 * 10)
        impact_score += pts
        sample_t4 = next((b.text for b in det_audit.bullet_audits if b.evidence_tier == "tier_4_verified_outcome"), "")
        deductions["impact_achievements"].append(
            ScoreDeductionItem(
                reason=f"{_n(t4, 'bullet')} {'reaches' if t4 == 1 else 'reach'} Tier 4 (verified outcome with concrete mechanism and metric)",
                points_impact=pts,
                source="deterministic_rule",
                evidence_ref=sample_t4[:110],
            )
        )
        evidence_map["impact_achievements"].append(f"Tier 4 outcome bullet: \"{sample_t4[:120]}\"")

    if t3 > 0:
        pts = min(20, t3 * 6)
        impact_score += pts
        sample_t3 = next((b.text for b in det_audit.bullet_audits if b.evidence_tier == "tier_3_concrete_evidence"), "")
        deductions["impact_achievements"].append(
            ScoreDeductionItem(
                reason=f"{_n(t3, 'bullet')} {'reaches' if t3 == 1 else 'reach'} Tier 3 (concrete operational scope or qualitative impact)",
                points_impact=pts,
                source="deterministic_rule",
                evidence_ref=sample_t3[:110],
            )
        )
        evidence_map["impact_achievements"].append(f"Tier 3 evidence bullet: \"{sample_t3[:120]}\"")

    if weak_duty_ratio >= 0.45:
        pen = -min(32, int(round(weak_duty_ratio * 38)))
        impact_score += pen
        sample_t1 = next(
            (b.text for b in det_audit.bullet_audits if b.evidence_tier in ("tier_0_generic", "tier_1_responsibility_only")),
            "",
        )
        deductions["impact_achievements"].append(
            ScoreDeductionItem(
                reason=f"{t0 + t1} of {total_b} bullets ({int(round(weak_duty_ratio * 100))}%) only state routine duties (Tier 0/1) with no demonstrated outcome",
                points_impact=pen,
                source="deterministic_rule",
                evidence_ref=sample_t1[:110],
            )
        )
        weaknesses_map["impact_achievements"].append(
            f"{t0 + t1}/{total_b} bullets read like a job description ('what you were supposed to do') rather than proving what changed because of your work."
        )
        improvements_map["impact_achievements"].append(
            "Convert duty-only bullets into [Action + Method + Measured/Observed Result] statements."
        )

    if det_audit.unanchored_claims_detected:
        pen = -min(20, len(det_audit.unanchored_claims_detected) * 7)
        impact_score += pen
        first_un = det_audit.unanchored_claims_detected[0]
        deductions["impact_achievements"].append(
            ScoreDeductionItem(
                reason=f"{_n(len(det_audit.unanchored_claims_detected), 'unanchored or implausible outcome claim')} detected ({first_un['reason']})",
                points_impact=pen,
                source="deterministic_rule",
                evidence_ref=first_un["text"][:110],
            )
        )
        weaknesses_map["impact_achievements"].append(
            f"Unverified/unanchored claim in [{first_un['section']}]: \"{first_un['text'][:90]}\" — {first_un['reason']}."
        )
        improvements_map["impact_achievements"].append(
            "Anchor every percentage or improvement claim with its baseline, final figure, or the specific change you made, or replace with concrete qualitative scope."
        )

    if not evidence_map["impact_achievements"]:
        evidence_map["impact_achievements"].append(
            f"Zero Tier 4 (quantified outcome) bullets detected across {total_b} evaluated statements."
        )
    scores["impact_achievements"] = max(10, min(96, impact_score))

    # -------------------------------------------------------------------------
    # 2. EXPERIENCE & PROJECT QUALITY (Primary owner of method depth, Tier 2+, and career-stage project rigour)
    # -------------------------------------------------------------------------
    exp_score = 52
    tech_detail_count = sum(1 for b in det_audit.bullet_audits if b.has_concrete_tech_or_method)
    tech_ratio = tech_detail_count / total_b

    has_exp = "experience" in sec_types
    has_proj = "projects" in sec_types

    if context.career_level == "student_graduate":
        if has_proj:
            exp_score += 12
            deductions["experience_project_quality"].append(
                ScoreDeductionItem(
                    reason="Early-career calibration: Dedicated Projects section present and evaluated alongside internships/coursework",
                    points_impact=12,
                    source="deterministic_rule",
                    evidence_ref="Projects section present",
                )
            )
            evidence_map["experience_project_quality"].append(
                "Candidate is calibrated at Student/Graduate stage: project, dissertation and research depth is credited alongside internship experience."
            )
    else:
        if not has_exp and not has_proj:
            exp_score -= 30
            deductions["experience_project_quality"].append(
                ScoreDeductionItem(
                    reason="Neither Work Experience nor Projects section detected",
                    points_impact=-30,
                    source="deterministic_rule",
                    evidence_ref="Missing Experience and Projects sections",
                )
            )
            weaknesses_map["experience_project_quality"].append(
                "CV lacks recognisable Work Experience and Projects sections."
            )

    if tech_ratio >= 0.65:
        pts = min(28, int(round(tech_ratio * 32)))
        exp_score += pts
        sample_tech = next((b.text for b in det_audit.bullet_audits if b.has_concrete_tech_or_method), "")
        deductions["experience_project_quality"].append(
            ScoreDeductionItem(
                reason=f"{tech_detail_count}/{total_b} bullets ({int(round(tech_ratio * 100))}%) say how the work was done, naming a specific method, tool or technique",
                points_impact=pts,
                source="deterministic_rule",
                evidence_ref=sample_tech[:110],
            )
        )
        evidence_map["experience_project_quality"].append(
            f"{tech_detail_count}/{total_b} bullets explain how the work was done with a named method, tool or technique."
        )
    elif tech_ratio < 0.35:
        pen = -18
        exp_score += pen
        deductions["experience_project_quality"].append(
            ScoreDeductionItem(
                reason=f"Only {tech_detail_count}/{total_b} bullets say how the work was done (the method, tool or technique used)",
                points_impact=pen,
                source="deterministic_rule",
                evidence_ref="Low specificity across experience/projects",
            )
        )
        weaknesses_map["experience_project_quality"].append(
            f"Only {tech_detail_count} of {total_b} bullets explain how the work was done rather than just naming the duty."
        )
        improvements_map["experience_project_quality"].append(
            "For each role and project, name the method, tool or technique you used, the scale of the work, and the decisions that were yours."
        )

    scores["experience_project_quality"] = max(12, min(96, exp_score))

    # -------------------------------------------------------------------------
    # 3. SKILLS CREDIBILITY (Primary owner of Skills section vs Experience/Project cross-verification)
    # -------------------------------------------------------------------------
    skills_score = 65
    claimed_n = len(skills_audit.claimed_skills)
    evidenced_n = len(skills_audit.evidenced_skills)
    unsupported_n = len(skills_audit.unsupported_skills)

    if claimed_n == 0 and evidenced_n == 0:
        skills_score = 25
        deductions["skills_credibility"].append(
            ScoreDeductionItem(
                reason="No verifiable technical or professional skills identified in CV",
                points_impact=-40,
                source="deterministic_rule",
                evidence_ref="No skills section or technical terms detected",
            )
        )
        weaknesses_map["skills_credibility"].append("No concrete technical or domain skills are evidenced in the CV.")
        improvements_map["skills_credibility"].append("Add a structured Skills section backed by project/work examples.")
    else:
        if evidenced_n > 0:
            pts = min(25, evidenced_n * 3)
            skills_score += pts
            deductions["skills_credibility"].append(
                ScoreDeductionItem(
                    reason=f"{_n(evidenced_n, 'skill')} verified with concrete evidence in Experience/Projects",
                    points_impact=pts,
                    source="deterministic_rule",
                    evidence_ref=", ".join(e["skill"] for e in skills_audit.evidenced_skills[:6]),
                )
            )
            evidence_map["skills_credibility"].append(
                f"Substantiated skills ({evidenced_n}): {', '.join(e['skill'] for e in skills_audit.evidenced_skills[:7])}."
            )

        if unsupported_n > 0:
            pen = -min(38, unsupported_n * 5)
            skills_score += pen
            deductions["skills_credibility"].append(
                ScoreDeductionItem(
                    reason=f"{_n(unsupported_n, 'listed skill')} {'has' if unsupported_n == 1 else 'have'} no supporting evidence in Experience or Projects",
                    points_impact=pen,
                    source="deterministic_rule",
                    evidence_ref=", ".join(skills_audit.unsupported_skills[:8]),
                )
            )
            weaknesses_map["skills_credibility"].append(
                f"Unsupported skills listed without evidence ({unsupported_n}): {', '.join(skills_audit.unsupported_skills[:8])}."
            )
            improvements_map["skills_credibility"].append(
                f"Either add concrete bullets showing where you used {', '.join(skills_audit.unsupported_skills[:4])} or cut them from the Skills section."
            )

        if skills_audit.overloaded_or_unsubstantiated_levels:
            for note in skills_audit.overloaded_or_unsubstantiated_levels[:2]:
                weaknesses_map["skills_credibility"].append(note)

        if skills_audit.omitted_demonstrated_skills:
            improvements_map["skills_credibility"].append(
                f"Add demonstrated skills currently missing from your Skills section: {', '.join(skills_audit.omitted_demonstrated_skills[:6])}."
            )

    scores["skills_credibility"] = max(15, min(96, skills_score))

    # -------------------------------------------------------------------------
    # 4. WRITING QUALITY & CLARITY (Primary owner of weak verbs, buzzwords, repetition, duplicate bullets)
    # -------------------------------------------------------------------------
    writing_score = 78
    weak_verb_bullets = [b for b in det_audit.bullet_audits if b.weak_verb_prefix]
    if weak_verb_bullets:
        pen = -min(24, len(weak_verb_bullets) * 5)
        writing_score += pen
        deductions["writing_clarity"].append(
            ScoreDeductionItem(
                reason=f"{_n(len(weak_verb_bullets), 'bullet')} {'opens' if len(weak_verb_bullets) == 1 else 'open'} with passive or weak phrasing ({weak_verb_bullets[0].weak_verb_prefix})",
                points_impact=pen,
                source="deterministic_rule",
                evidence_ref=weak_verb_bullets[0].text[:100],
            )
        )
        weaknesses_map["writing_clarity"].append(
            f"{_n(len(weak_verb_bullets), 'bullet')} {'starts' if len(weak_verb_bullets) == 1 else 'start'} with passive phrasing like '{weak_verb_bullets[0].weak_verb_prefix}' instead of direct ownership verbs."
        )
        improvements_map["writing_clarity"].append(
            "Replace passive openings ('Worked on', 'Responsible for', 'Helped with') with precise verbs indicating your exact role."
        )

    if det_audit.buzzwords_detected:
        pen = -min(20, len(det_audit.buzzwords_detected) * 4)
        writing_score += pen
        deductions["writing_clarity"].append(
            ScoreDeductionItem(
                reason=f"{_n(len(det_audit.buzzwords_detected), 'empty buzzword or cliché', 'empty buzzwords or clichés')} detected",
                points_impact=pen,
                source="deterministic_rule",
                evidence_ref=", ".join(det_audit.buzzwords_detected[:6]),
            )
        )
        weaknesses_map["writing_clarity"].append(
            f"Contains unsubstantiated buzzwords/clichés: {', '.join(det_audit.buzzwords_detected[:6])}."
        )
        improvements_map["writing_clarity"].append(
            "Delete self-congratulatory adjectives ('hard-working', 'passionate', 'results-driven') and let factual achievements prove competence."
        )

    if det_audit.duplicate_bullet_pairs:
        pen = -min(18, len(det_audit.duplicate_bullet_pairs) * 8)
        writing_score += pen
        pair = det_audit.duplicate_bullet_pairs[0]
        deductions["writing_clarity"].append(
            ScoreDeductionItem(
                reason=f"{_n(len(det_audit.duplicate_bullet_pairs), 'duplicated or near-identical bullet pair')} detected ({pair['similarity']} match)",
                points_impact=pen,
                source="deterministic_rule",
                evidence_ref=pair["second_text"][:100],
            )
        )
        weaknesses_map["writing_clarity"].append(
            f"Duplicate/repetitive bullet detected ({pair['similarity']} similarity): \"{pair['second_text'][:80]}\"."
        )
        improvements_map["writing_clarity"].append("Cut or consolidate duplicated bullets across roles.")

    if det_audit.repeated_opening_verbs:
        rep_str = ", ".join(f"'{k}' ({v}x)" for k, v in det_audit.repeated_opening_verbs.items())
        writing_score -= 6
        deductions["writing_clarity"].append(
            ScoreDeductionItem(
                reason=f"Repetitive opening words across bullets: {rep_str}",
                points_impact=-6,
                source="deterministic_rule",
                evidence_ref=rep_str,
            )
        )
        weaknesses_map["writing_clarity"].append(f"Overused opening words: {rep_str}.")

    if not weaknesses_map["writing_clarity"]:
        evidence_map["writing_clarity"].append(
            "Clean, direct British English phrasing with strong action verbs and zero cliché buzzwords."
        )
    else:
        evidence_map["writing_clarity"].append(
            f"Audited {total_b} bullets (average length {det_audit.avg_bullet_words} words)."
        )
    scores["writing_clarity"] = max(15, min(96, writing_score))

    # -------------------------------------------------------------------------
    # 5. STRUCTURE & READABILITY (Primary owner of section ordering, word count, bullet length balance)
    # -------------------------------------------------------------------------
    struct_score = 82
    wc = det_audit.total_words
    if wc < 70 or (wc < 130 and det_audit.total_bullets < 3):
        penalty = -28 if wc < 70 else -16
        struct_score += penalty
        deductions["structure_readability"].append(
            ScoreDeductionItem(
                reason=f"Under-length CV ({wc} words, {det_audit.total_bullets} reviewed statements) does not give a recruiter enough evidence",
                points_impact=penalty,
                source="deterministic_rule",
                evidence_ref=f"{wc} words across {_n(extracted_cv.diagnostics.page_count, 'page')}",
            )
        )
        weaknesses_map["structure_readability"].append(
            f"The document has {wc} words and only {det_audit.total_bullets} reviewed statements."
        )
        improvements_map["structure_readability"].append(
            "Expand the roles and projects you can evidence. Do not add length without adding proof."
        )
    elif wc > 1100:
        struct_score -= 15
        deductions["structure_readability"].append(
            ScoreDeductionItem(
                reason=f"Overlong document ({wc} words) dilutes key evidence and slows recruiter scanning",
                points_impact=-15,
                source="deterministic_rule",
                evidence_ref=f"{wc} words",
            )
        )
        weaknesses_map["structure_readability"].append(
            f"At {wc} words, the CV is overly verbose; recruiters spend 15–30 seconds on an initial scan."
        )

    if det_audit.short_bullets_count >= 2:
        pen = -min(16, det_audit.short_bullets_count * 4)
        struct_score += pen
        deductions["structure_readability"].append(
            ScoreDeductionItem(
                reason=f"{_n(det_audit.short_bullets_count, 'fragmented bullet')} under 8 words",
                points_impact=pen,
                source="deterministic_rule",
                evidence_ref=f"{det_audit.short_bullets_count} short bullets",
            )
        )
        weaknesses_map["structure_readability"].append(
            f"{det_audit.short_bullets_count} bullets are under 8 words and too telegraphic to convey context."
        )

    if det_audit.overlong_bullets_count >= 2:
        pen = -min(14, det_audit.overlong_bullets_count * 4)
        struct_score += pen
        deductions["structure_readability"].append(
            ScoreDeductionItem(
                reason=f"{_n(det_audit.overlong_bullets_count, 'dense wall-of-text bullet')} over 38 words",
                points_impact=pen,
                source="deterministic_rule",
                evidence_ref=f"{det_audit.overlong_bullets_count} overlong bullets",
            )
        )
        weaknesses_map["structure_readability"].append(
            f"{det_audit.overlong_bullets_count} bullets exceed 38 words and should be split or condensed for scannability."
        )

    # Check section ordering for career stage
    if context.career_level in ("mid_level", "senior_lead", "executive") and "education" in sec_types and "experience" in sec_types:
        edu_idx = sec_types.index("education")
        exp_idx = sec_types.index("experience")
        if edu_idx < exp_idx:
            struct_score -= 10
            deductions["structure_readability"].append(
                ScoreDeductionItem(
                    reason="Education section is placed above Work Experience for an experienced candidate",
                    points_impact=-10,
                    source="deterministic_rule",
                    evidence_ref="Section order: Education before Work Experience",
                )
            )
            weaknesses_map["structure_readability"].append(
                "Education appears above Work Experience despite targeting an experienced role."
            )
            improvements_map["structure_readability"].append(
                "Move Work Experience immediately below your Professional Summary so commercial track record leads the CV."
            )

    evidence_map["structure_readability"].append(
        f"{extracted_cv.diagnostics.section_count} sections, {det_audit.total_bullets} bullets, {wc} words ({_n(extracted_cv.diagnostics.page_count, 'page')})."
    )
    scores["structure_readability"] = max(15, min(96, struct_score))

    # -------------------------------------------------------------------------
    # 6. ATS COMPATIBILITY (Primary owner of verified file layout, header/footer, contact & heading checks)
    # -------------------------------------------------------------------------
    ats_score = 92
    for issue in extracted_cv.diagnostics.ats_issues:
        if issue.issue_type != "verified_document_issue":
            continue
        if issue.severity == "high":
            pen = -22
        elif issue.severity == "medium":
            pen = -12
        else:
            pen = -6
        ats_score += pen
        deductions["ats_compatibility"].append(
            ScoreDeductionItem(
                reason=issue.title,
                points_impact=pen,
                source="deterministic_rule",
                evidence_ref=issue.evidence[:110],
            )
        )
        weaknesses_map["ats_compatibility"].append(f"{issue.title}: {issue.evidence}")
        improvements_map["ats_compatibility"].append(issue.remediation)

    if ats_score >= 85:
        evidence_map["ats_compatibility"].append(
            "Single-column linear flow, standard section headings, and parsable contact details verified in document structure."
        )
    scores["ats_compatibility"] = max(10, min(98, ats_score))

    # -------------------------------------------------------------------------
    # 7. RELEVANCE & ROLE ALIGNMENT (Combines target role/JD alignment with career-stage positioning)
    # -------------------------------------------------------------------------
    rel_score = 62

    def _rel(points: int, reason: str, ref: str) -> None:
        nonlocal rel_score
        rel_score += points
        deductions["relevance_alignment"].append(
            ScoreDeductionItem(reason=reason, points_impact=points, source="deterministic_rule", evidence_ref=ref)
        )

    if role_fit:
        fit = int(role_fit.get("fit", 0))
        role_title = role_fit.get("title", "the target role")
        basis = (
            "your stated target"
            if role_fit.get("stated")
            else f"the most likely role inferred from your CV, {role_fit.get('confidence', 'medium')} confidence"
        )
        bands = ((70, 16, "Strong"), (55, 8, "Good"), (40, 0, "Partial"), (25, -10, "Weak"), (0, -18, "Very limited"))
        points, band = next((p, b) for floor, p, b in bands if fit >= floor)
        if jd_alignment is not None:
            points = int(round(points / 2))
        if points:
            note = "; halved because the job description's own requirements take precedence" if jd_alignment is not None else ""
            _rel(points, f"{band} evidence coverage for {role_title} ({basis}){note}", f"{fit}% weighted competency coverage")
        evidence_map["relevance_alignment"].append(
            f"Positioning measured against {role_title} ({basis}): {fit}% of weighted core competencies are evidenced."
        )
        if fit < 40:
            weaknesses_map["relevance_alignment"].append(
                f"The CV evidences only {fit}% of what {role_title} recruiters typically screen for."
            )
            for gap in role_fit.get("gaps", [])[:2]:
                improvements_map["relevance_alignment"].append(f"Close this gap for {role_title}: {gap}")
    elif context.target_job_title:
        title_tokens = [
            t.lower()
            for t in re.split(r"\W+", context.target_job_title)
            if len(t) > 2 and t.lower() not in {"senior", "junior", "mid", "lead", "graduate", "intern", "the", "and"}
        ]
        matched_tokens = [t for t in title_tokens if t in extracted_cv.raw_text.lower()]
        if title_tokens and len(matched_tokens) == len(title_tokens):
            rel_score += 14
            deductions["relevance_alignment"].append(
                ScoreDeductionItem(
                    reason=f"CV explicitly evidences core role domain terms for '{context.target_job_title}'",
                    points_impact=14,
                    source="deterministic_rule",
                    evidence_ref=", ".join(matched_tokens),
                )
            )
            evidence_map["relevance_alignment"].append(
                f"Direct domain alignment with target role '{context.target_job_title}'."
            )
        elif title_tokens and not matched_tokens:
            rel_score -= 18
            deductions["relevance_alignment"].append(
                ScoreDeductionItem(
                    reason=f"Target role '{context.target_job_title}' keywords do not appear in CV text",
                    points_impact=-18,
                    source="deterministic_rule",
                    evidence_ref=f"Missing role terms: {', '.join(title_tokens)}",
                )
            )
            weaknesses_map["relevance_alignment"].append(
                f"The CV does not clearly position you for '{context.target_job_title}'."
            )
            improvements_map["relevance_alignment"].append(
                f"Tailor your summary and top experience bullets to foreground evidence relevant to '{context.target_job_title}'."
            )

    if jd_alignment is not None:
        jd_points = next(p for floor, p in ((75, 10), (55, 3), (40, -6), (0, -14)) if jd_alignment >= floor)
        _rel(jd_points, f"{jd_alignment}% of the job description's weighted requirements are evidenced (Essential counts double)", "Job description mapping")
        if jd_points < 0:
            weaknesses_map["relevance_alignment"].append(
                f"Only {jd_alignment}% of the job description's weighted requirements are clearly evidenced."
            )

    if not context.job_description.strip():
        if role_fit:
            target_phrase = role_fit.get("title", "the target role") + ("" if role_fit.get("stated") else " (inferred from your CV)")
        else:
            target_phrase = f"'{context.target_job_title}'" if context.target_job_title else "general expectations for your career stage"
        uncertainty_map["relevance_alignment"] = (
            f"No job description was supplied, so relevance is measured against typical requirements for {target_phrase}, "
            "not a specific employer's vacancy."
        )

    if not evidence_map["relevance_alignment"]:
        evidence_map["relevance_alignment"].append(
            f"Assessed positioning across {len(extracted_cv.sections)} sections for career stage '{context.career_level}'."
        )
    scores["relevance_alignment"] = max(15, min(95, rel_score))

    return (
        scores,
        deductions,
        evidence_map,
        weaknesses_map,
        improvements_map,
        uncertainty_map,
    )
