import re
from datetime import date
from typing import Dict, List, Optional, Tuple

from backend.profiles import MATCH_ORDER, PROFILES, PROFILES_BY_ID, Competency, RoleProfile
from backend.schemas import (
    AnalysisContext,
    DeterministicCVAudit,
    ExtractedBullet,
    ExtractedCV,
    RoleCompetencyEvidence,
    RoleTarget,
    RoleTargetingResult,
)

YEAR_RANGE = re.compile(r"\b((?:19|20)\d{2})\s*(?:-|–|—|to)\s*((?:19|20)\d{2}|present|current|now|ongoing)\b", re.I)
SENIOR_TITLE = re.compile(r"\b(?:senior|lead|principal|staff|head\s+of|manager)\b", re.I)
EXEC_TITLE = re.compile(r"\b(?:director|vp|vice\s+president|chief|cto|ceo|cfo|coo|founder)\b", re.I)

EVIDENCE_SECTIONS = {"experience", "projects", "additional"}
MENTION_SECTIONS = {"summary", "education", "certifications"}
TIER_RANK = {
    "tier_0_generic": 0,
    "tier_1_responsibility_only": 1,
    "tier_2_technical_detail": 2,
    "tier_3_concrete_evidence": 3,
    "tier_4_verified_outcome": 4,
}
COVERAGE_VALUE = {"in_experience": 1.0, "summary_only": 0.5, "skills_list_only": 0.3, "missing": 0.0}
LEVEL_NAMES = {
    "student_graduate": "student / graduate",
    "junior": "junior",
    "mid_level": "mid-level",
    "senior_lead": "senior / lead",
    "career_changer": "career changer",
    "executive": "executive",
}

METHOD_NOTE = (
    "Roles are inferred by matching the CV text against built-in role profiles. Fit counts where each "
    "competency is evidenced: experience or projects count fully, the summary, education or a heading count "
    "half, and the skills list alone counts 30%. Essential competencies count double. Fit is a measure of "
    "coverage, not the probability of an interview."
)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def _clip(text: str, limit: int = 150) -> str:
    text = text.strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _year_ranges(lines: List[str]) -> List[Tuple[int, int]]:
    current = date.today().year
    ranges = []
    for line in lines:
        for start_raw, end_raw in YEAR_RANGE.findall(line):
            start = int(start_raw)
            end = current if not end_raw[:1].isdigit() else int(end_raw)
            if start <= end <= current + 6:
                ranges.append((start, end))
    return ranges


def _merged_years(ranges: List[Tuple[int, int]]) -> int:
    total, last_end = 0, None
    for start, end in sorted(ranges):
        if last_end is not None and start < last_end:
            start = last_end
        if end > start:
            total += end - start
        last_end = max(end, last_end or end)
    return total


def infer_career_level(extracted: ExtractedCV) -> Tuple[str, str]:
    experience_lines, education_lines, titles = [], [], []
    for section in extracted.sections:
        if section.normalized_type == "experience":
            experience_lines.extend(section.raw_lines)
            titles.extend(item.text for item in section.items if not item.is_bullet and item.entry_title == item.text)
        elif section.normalized_type == "education":
            education_lines.extend(section.raw_lines)

    years = _merged_years(_year_ranges(experience_lines))
    education_end = max((end for _start, end in _year_ranges(education_lines)), default=None)
    recent_study = education_end is not None and education_end >= date.today().year - 2
    title_text = " ".join(titles)
    span = f"about {years} year{'s' if years != 1 else ''} of dated experience"

    if EXEC_TITLE.search(title_text) and years >= 8:
        return "executive", f"Inferred from {span} and an executive-level job title."
    if (SENIOR_TITLE.search(title_text) and years >= 4) or years >= 8:
        return "senior_lead", f"Inferred from {span}" + (" and a senior or management title." if SENIOR_TITLE.search(title_text) else ".")
    if not experience_lines and education_lines:
        return "student_graduate", "Inferred because the CV has no work-experience section and leads with education or projects."
    if years < 2 and recent_study:
        return "student_graduate", f"Inferred from {span} and education ending in {education_end}."
    if years < 3:
        return "junior", f"Inferred from {span}."
    return "mid_level", f"Inferred from {span} without senior job titles."


def _pools(extracted: ExtractedCV) -> Dict[str, List[ExtractedBullet]]:
    pools: Dict[str, List[ExtractedBullet]] = {"evidence": [], "headers": [], "mentions": [], "skills": []}
    for section in extracted.sections:
        kind = section.normalized_type
        for item in section.items:
            is_header = not item.is_bullet and item.entry_title == item.text
            if kind in EVIDENCE_SECTIONS:
                pools["headers" if is_header else "evidence"].append(item)
            elif kind == "skills":
                pools["skills"].append(item)
            elif kind in MENTION_SECTIONS:
                pools["mentions"].append(item)
    return pools


def _assess(comp: Competency, pools: Dict[str, List[ExtractedBullet]], tiers: Dict[str, str]) -> RoleCompetencyEvidence:
    base = {"key": comp.key, "label": comp.label, "essential": comp.essential}
    best, best_rank = None, -1
    for item in pools["evidence"]:
        if comp.pattern.search(item.text):
            rank = TIER_RANK.get(tiers.get(item.bullet_id, ""), 1)
            if rank > best_rank:
                best, best_rank = item, rank
    if best is not None:
        depth = "proven" if best_rank >= 3 else "described" if best_rank == 2 else "mentioned"
        return RoleCompetencyEvidence(**base, coverage="in_experience", depth=depth, evidence_quote=_clip(best.text), bullet_id=best.bullet_id)
    for item in pools["mentions"] + pools["headers"]:
        if comp.pattern.search(item.text):
            return RoleCompetencyEvidence(**base, coverage="summary_only", depth="mentioned", evidence_quote=_clip(item.text), bullet_id=item.bullet_id)
    for item in pools["skills"]:
        match = comp.pattern.search(item.text)
        if match:
            return RoleCompetencyEvidence(**base, coverage="skills_list_only", depth="mentioned", evidence_quote=match.group(0), bullet_id=item.bullet_id)
    return RoleCompetencyEvidence(**base, coverage="missing", depth="none")


def _gap_text(ev: RoleCompetencyEvidence) -> Optional[str]:
    if ev.coverage == "missing":
        return f"{ev.label}: no evidence anywhere in the CV."
    if ev.coverage == "skills_list_only":
        return f"{ev.label}: '{ev.evidence_quote}' is listed in your skills but never shown in a role or project."
    if ev.coverage == "summary_only":
        return f"{ev.label}: mentioned in your summary, education or a heading, but not shown in a role or project."
    if ev.depth == "mentioned":
        return f"{ev.label}: appears only as a duty, with no detail, scale or result."
    return None


def _gap_order(ev: RoleCompetencyEvidence) -> Tuple[int, int]:
    severity = {"missing": 0, "skills_list_only": 1, "summary_only": 2, "in_experience": 3}[ev.coverage]
    return (0 if ev.essential else 1, severity)


def _readiness(fit: int, strength: int) -> str:
    if fit >= 70 and strength >= 45:
        return "Apply now"
    if fit >= 50:
        return "Apply with targeted edits"
    if fit >= 30:
        return "Stretch: build evidence first"
    return "Long-term pivot"


def _confidence(fit: int, title_bonus: int, signal_hits: int) -> str:
    if fit >= 60 and (title_bonus >= 10 or signal_hits >= 4):
        return "high"
    if fit >= 40 or (fit >= 30 and title_bonus >= 10):
        return "medium"
    return "low"


def match_profile_to_title(title: str) -> Optional[RoleProfile]:
    """Match a job title to a profile, preferring the most specific hit.

    Specificity is the length of the matched text, so "senior backend engineer" resolves to the backend profile
    rather than the general software-engineer profile even though both patterns match.
    """
    if not title.strip():
        return None
    best, best_len = None, 0
    for role_id in MATCH_ORDER:
        hit = PROFILES_BY_ID[role_id].title_pattern.search(title)
        if hit and len(hit.group(0)) > best_len:
            best, best_len = PROFILES_BY_ID[role_id], len(hit.group(0))
    return best


def _evaluate(profile: RoleProfile, pools, tiers, raw_text: str) -> Tuple[RoleTarget, float]:
    evidence = [_assess(comp, pools, tiers) for comp in profile.competencies]
    weights = [2 if ev.essential else 1 for ev in evidence]
    fit = round(100 * sum(w * COVERAGE_VALUE[ev.coverage] for w, ev in zip(weights, evidence)) / sum(weights))
    depth_value = {"proven": 1.0, "described": 0.6, "mentioned": 0.35, "none": 0.0}
    strength = round(100 * sum(
        w * (depth_value[ev.depth] if ev.coverage == "in_experience" else 0.12 if ev.coverage != "missing" else 0.0)
        for w, ev in zip(weights, evidence)
    ) / sum(weights))

    title_bonus, title_reason = 0, ""
    for pool_name, bonus in (("headers", 18), ("mentions", 10)):
        hit = next((profile.title_pattern.search(i.text) for i in pools[pool_name] if profile.title_pattern.search(i.text)), None)
        if hit:
            title_bonus, title_reason = bonus, f"Your CV's titles or summary mention '{hit.group(0)}'."
            break
    if not title_bonus and profile.title_pattern.search(raw_text):
        title_bonus, title_reason = 5, f"Your CV mentions '{profile.title_pattern.search(raw_text).group(0)}'."
    signals = [s.lower() for s in profile.signal_pattern.findall(raw_text)]
    signal_bonus = min(10.0, 1.5 * len(signals))

    shown = [ev.label for ev in evidence if ev.coverage == "in_experience"]
    why = [title_reason] if title_reason else []
    why.append(f"{len(shown)} of {len(evidence)} core competencies are shown in experience or projects" + (f": {', '.join(shown[:4])}." if shown else "."))
    if signals:
        why.append(f"Recurring terms: {', '.join(sorted(set(signals))[:5])}.")

    gaps = sorted((ev for ev in evidence if _gap_text(ev)), key=_gap_order)
    comps = {c.key: c for c in profile.competencies}
    next_steps = [comps[ev.key].action for ev in gaps if ev.coverage != "in_experience"][:3]
    if not next_steps and gaps:
        next_steps = [f"Rewrite the {gaps[0].label.lower()} bullet with its scale and result."]
    if not next_steps:
        next_steps = ["Lead with this role in your summary and order bullets by relevance to it."]

    target = RoleTarget(
        role_id=profile.role_id,
        title=profile.title,
        family=profile.family,
        fit_percentage=max(0, min(100, fit)),
        evidence_strength=max(0, min(100, strength)),
        confidence=_confidence(fit, title_bonus, len(signals)),  # type: ignore[arg-type]
        readiness=_readiness(fit, strength),
        why_inferred=why,
        competencies=evidence,
        benchmark=profile.benchmark,
        writing_focus=profile.writing_focus,
        top_gaps=[_gap_text(ev) for ev in gaps][:4],
        next_steps=next_steps,
    )
    return target, fit + title_bonus + signal_bonus, bool(title_bonus or signals)


def infer_role_targets(extracted: ExtractedCV, context: AnalysisContext, audit: DeterministicCVAudit) -> RoleTargetingResult:
    pools = _pools(extracted)
    tiers = {b.bullet_id: b.evidence_tier for b in audit.bullet_audits}
    raw_text = extracted.raw_text

    specified_title = context.target_job_title.strip()
    title_source = "you entered"
    if not specified_title and context.job_description.strip():
        jd_profile = match_profile_to_title(context.job_description[:400])
        if jd_profile:
            specified_title, title_source = jd_profile.title, "taken from the job description"
    user_profile = match_profile_to_title(specified_title)
    forced = {pid for pid in (context.pinned_role_id, user_profile.role_id if user_profile else "") if pid in PROFILES_BY_ID}

    rows: List[Tuple[float, RoleTarget, bool]] = []
    for profile in PROFILES:
        if context.career_level not in profile.levels and profile.role_id not in forced:
            continue
        target, rank, relevant = _evaluate(profile, pools, tiers, raw_text)
        rows.append((rank, target, relevant))
    rows.sort(key=lambda row: row[0], reverse=True)
    # A role only qualifies if the CV genuinely resembles it (a title or domain signal hit) or the user chose it.
    # Otherwise a CV would be labelled with whatever profile happens to score least badly.
    scored = [row for row in rows if row[2] or row[1].role_id in forced] or rows[:1]

    primary_id = context.pinned_role_id if context.pinned_role_id in PROFILES_BY_ID else ""
    if not primary_id and user_profile:
        primary_id = user_profile.role_id
    if not primary_id and scored:
        primary_id = scored[0][1].role_id

    others = [row for row in scored if row[1].role_id != primary_id]
    candidates = [t for _r, t, _rel in scored if t.role_id == primary_id]
    candidates += [t for _r, t, relevant in others if relevant][:3]
    if len(candidates) < 3:
        candidates += [t for _r, t, relevant in others if not relevant][: 3 - len(candidates)]
    for target in candidates:
        target.is_primary = target.role_id == primary_id
        if user_profile and target.role_id == user_profile.role_id:
            target.is_user_target = True
            target.why_inferred.insert(0, f"Target {title_source}: '{specified_title}'.")

    note = METHOD_NOTE
    if specified_title and not user_profile:
        note += f" No built-in profile matches '{specified_title}', so the roles below are the closest evidence-based matches."
    return RoleTargetingResult(
        role_was_specified=bool(specified_title),
        specified_title=specified_title,
        specified_title_matched_profile=user_profile is not None,
        primary_role_id=primary_id,
        primary_title=PROFILES_BY_ID[primary_id].title if primary_id else "",
        candidates=candidates,
        career_level_used=context.career_level,
        career_level_source=context.career_level_source,
        career_level_reason=context.career_level_reason,
        method_note=note,
    )


def primary_target(result: Optional[RoleTargetingResult]) -> Optional[RoleTarget]:
    if result is None:
        return None
    return next((c for c in result.candidates if c.is_primary), None)


def role_fit_for_scoring(result: Optional[RoleTargetingResult]) -> Optional[dict]:
    primary = primary_target(result)
    if primary is None or (result.role_was_specified and not result.specified_title_matched_profile):
        return None
    if not primary.is_user_target and primary.confidence == "low":
        return None
    return {
        "title": primary.title,
        "fit": primary.fit_percentage,
        "stated": primary.is_user_target,
        "confidence": primary.confidence,
        "gaps": primary.top_gaps[:2],
    }


def describe_level(level: str) -> str:
    return LEVEL_NAMES.get(level, level.replace("_", " "))


def merge_semantic_role_hypotheses(result: RoleTargetingResult, payload: Optional[dict], raw_text: str) -> RoleTargetingResult:
    hypotheses = payload.get("role_hypotheses") if isinstance(payload, dict) else None
    if not isinstance(hypotheses, list):
        return result
    corpus = _norm(raw_text)
    known = {c.title.lower() for c in result.candidates}
    for hypothesis in hypotheses[:6]:
        if not isinstance(hypothesis, dict):
            continue
        title = str(hypothesis.get("title", "")).strip()[:80]
        quote = str(hypothesis.get("evidence_quote", "")).strip()
        if not title or len(quote) < 12 or title.lower() in known or _norm(quote) not in corpus:
            continue
        result.semantic_suggestions.append(f"{title}: suggested by the AI model because your CV says \"{_clip(quote, 140)}\".")
        if len(result.semantic_suggestions) >= 3:
            break
    return result
