import re
from datetime import date
from typing import Dict, List, Optional

from backend.role_inference import primary_target
from backend.profiles import PROFILES_BY_ID
from backend.schemas import (
    AnalysisContext,
    DeterministicCVAudit,
    DevelopmentAction,
    ElevationPlan,
    ExtractedCV,
    RecommendationItem,
    RoleTarget,
    RoleTargetingResult,
    SkillsCredibilityAudit,
    WritingUpgrade,
)

EVIDENCE_TYPES = {"experience", "projects", "additional"}
CODE_FAMILIES = {"Software engineering", "Infrastructure and support", "Data and AI", "Hardware and robotics"}
TIMEFRAME_ORDER = {"This week": 0, "Next 30 days": 1, "Next 90 days": 2}
VERB_BANK = {
    "Software engineering": "Built, Designed, Shipped, Refactored, Automated, Profiled, Reduced",
    "Infrastructure and support": "Automated, Provisioned, Migrated, Monitored, Hardened, Resolved, Restored",
    "Data and AI": "Analysed, Modelled, Trained, Evaluated, Forecast, Visualised, Pipelined",
    "Security": "Investigated, Detected, Hardened, Assessed, Remediated, Contained, Verified",
    "Hardware and robotics": "Designed, Built, Commissioned, Integrated, Calibrated, Measured, Programmed",
    "Product and design": "Defined, Prioritised, Shipped, Researched, Simplified, Measured, Launched",
}
STAGE_ACTIONS = {
    "student_graduate": ("Apply for an internship, placement or open-source contribution",
                         "Work reviewed by real users or maintainers turns project claims into work evidence. Aim for one application or contribution a week.",
                         "Next 90 days", "Medium", "Contributed [feature/fix] to [project], reviewed and merged by its maintainers."),
    "junior": ("Ask for one stretch responsibility in your current role",
               "Owning something specific, such as training a starter, a weekly report or a small process, gives you a bullet nobody else with your title has.",
               "Next 30 days", "Low", "Took ownership of [responsibility], [result]."),
    "mid_level": ("Lead one piece of work end to end",
                  "Pick a problem with a measurable before and after, and own it from proposal to result.",
                  "Next 90 days", "High", "Led [initiative] from proposal to launch, [measured result]."),
    "senior_lead": ("Record team-level outcomes, not just your own",
                    "Track hiring, mentoring, delivery and budget results for the teams you lead.",
                    "Next 30 days", "Low", "Led a team of [number] that delivered [outcome]."),
    "career_changer": ("Build one bridge project that uses your previous field",
                       "Solving a problem from your old domain with your new skills is the most persuasive evidence for a pivot.",
                       "Next 90 days", "High", "Built [project] to solve [problem from your previous role], used by [who]."),
    "executive": ("Quantify organisation-level results",
                  "Revenue, cost, headcount, transformation timelines and decisions you drove at board level.",
                  "Next 30 days", "Low", "Grew [business unit] from [before] to [after] over [period]."),
}
HONESTY_NOTE = (
    "Everything under 'Add now, if true' and 'Things to begin' is a prompt, not a claim to add. Only put something "
    "on your CV once it is true and you can discuss it in an interview. Text in [brackets] is a template to fill with "
    "real details; exports stay blocked until every bracket is resolved."
)


def _join(items: List[str]) -> str:
    if len(items) <= 1:
        return "".join(items)
    last_sep = ", and " if any(" and " in item for item in items) else " and "
    return ", ".join(items[:-1]) + last_sep + items[-1]


def _n(count: int, singular: str) -> str:
    return f"{count} {singular if count == 1 else singular + 's'}"


def _verb(count: int, singular: str, plural: str) -> str:
    return singular if count == 1 else plural


def _identity(extracted: ExtractedCV, level: str) -> str:
    for wanted in ("experience", "education"):
        for section in extracted.sections:
            if section.normalized_type != wanted:
                continue
            for item in section.items:
                if item.is_bullet or item.entry_title != item.text:
                    continue
                head = re.split(r"\s*(?:\||,|\sat\s|\s[-–—]\s)\s*", item.text)[0].strip()
                if wanted == "experience":
                    return head
                years = [int(y) for y in re.findall(r"\b(?:19|20)\d{2}\b", item.text)]
                return f"{head} {'student' if years and max(years) >= date.today().year else 'graduate'}"
    return ""


def _summary_example(
    extracted: ExtractedCV, context: AnalysisContext, primary: Optional[RoleTarget], skills: SkillsCredibilityAudit
) -> str:
    identity = _identity(extracted, context.career_level) or "[Your current role or degree]"
    shown = [item["skill"] for item in skills.evidenced_skills if item.get("skill")][:3]
    if not shown and primary:
        strong = [c.label.lower() for c in primary.competencies if c.coverage == "in_experience" and c.depth in ("proven", "described")]
        shown = (strong or [c.label.lower() for c in primary.competencies if c.coverage == "in_experience"])[:3]
    evidence = _join(shown) if shown else "[the two things you can best prove]"
    target = primary.title if primary else "[target role]"
    return f"{identity} with hands-on evidence in {evidence}. Targeting {target} roles, bringing [your single strongest result]."


def _first_rec(recs: List[RecommendationItem], action: str, bullet_ids: Optional[set] = None) -> Optional[RecommendationItem]:
    for rec in recs:
        if rec.action == action and rec.original_text and rec.suggested_text and (bullet_ids is None or rec.bullet_id in bullet_ids):
            return rec
    return None


def _writing_upgrades(extracted, audit, skills, context, primary, recs) -> List[WritingUpgrade]:
    section_types = {s.title: s.normalized_type for s in extracted.sections}
    work = [b for b in audit.bullet_audits if section_types.get(b.section_name) in EVIDENCE_TYPES]
    duty_ids = {b.bullet_id for b in work if b.evidence_tier in ("tier_0_generic", "tier_1_responsibility_only")}
    detail_ids = {b.bullet_id for b in work if b.evidence_tier == "tier_2_technical_detail"}
    ups: List[WritingUpgrade] = []

    def add(priority, title, problem, why, how, rec=None, before="", after="", count=0):
        ups.append(WritingUpgrade(
            upgrade_id=f"wu_{len(ups) + 1}", priority=priority, title=title, problem=problem, why_it_matters=why, how_to_fix=how,
            example_before=rec.original_text if rec else before, example_after=rec.suggested_text if rec else after, affected_count=count,
        ))

    if duty_ids:
        add("critical" if len(duty_ids) >= max(2, len(work) / 2) else "high", "Turn duties into achievements",
            f"{len(duty_ids)} of {_n(len(work), 'experience and project bullet')} {_verb(len(duty_ids), 'describes', 'describe')} duties rather than what you did and what happened.",
            "Recruiters skim for scope and outcome. A duty list reads the same as every other applicant with the same title.",
            "Use: action verb + what you did + how or with what + scale + result. If you cannot measure the result, give the scale (how many, how often, how big).",
            _first_rec(recs, "rewrite", duty_ids), count=len(duty_ids))
    if detail_ids:
        add("high", "Finish bullets with the result",
            f"{_n(len(detail_ids), 'bullet')} {_verb(len(detail_ids), 'shows', 'show')} method or detail but {_verb(len(detail_ids), 'stops', 'stop')} before the outcome.",
            "Detail proves you were there; the result proves it mattered. Without it, a strong bullet reads like a task description.",
            "Add the 'so what': what changed, for whom, by how much. Use real figures only. If you don't have one, state the scale instead.",
            _first_rec(recs, "rewrite", detail_ids), count=len(detail_ids))
    if audit.unanchored_claims_detected:
        add("critical", "Back up or soften unproven claims",
            f"{_n(len(audit.unanchored_claims_detected), 'claim')} (such as unexplained percentages or absolute statements) {_verb(len(audit.unanchored_claims_detected), 'has', 'have')} no baseline, scope or method.",
            "Screeners treat unexplained numbers and absolutes as a credibility risk, and interviewers will probe them.",
            "Give the baseline and how it was measured ('from X to Y, measured by Z'), or soften the claim to what you can defend.",
            _first_rec(recs, "verify"), count=len(audit.unanchored_claims_detected))
    has_summary = any(s.normalized_type == "summary" for s in extracted.sections)
    summary_line = next((i.text for s in extracted.sections if s.normalized_type == "summary" for i in s.items), "")
    if audit.buzzwords_detected or not has_summary:
        add("high" if audit.buzzwords_detected else "medium",
            "Replace self-descriptions with evidence" if has_summary else "Add a targeted two-line summary",
            (f"The CV relies on self-descriptions recruiters ignore: {', '.join(audit.buzzwords_detected[:6])}." if audit.buzzwords_detected
             else "There is no summary, so the reader has to work out what role you are aiming for."),
            "The summary is read first. It should state what you are, what you can prove, and what you want, using facts already in the CV.",
            "Formula: [current role or degree] + [the two things you can best prove] + [target role]. No adjectives you cannot evidence.",
            before=summary_line, after=_summary_example(extracted, context, primary, skills), count=len(audit.buzzwords_detected))
    repeated = {verb: n for verb, n in audit.repeated_opening_verbs.items() if n >= 2}
    if repeated:
        verb, count = max(repeated.items(), key=lambda kv: kv[1])
        family = primary.family if primary else ""
        add("medium", "Vary how bullets start",
            f"{count} bullets start with '{verb}'" + (f", and {len(repeated) - 1} other openings repeat." if len(repeated) > 1 else "."),
            "Repeated openings make separate achievements blur into one.",
            f"Start each bullet with the verb that best describes your contribution. Verbs that suit {primary.title if primary else 'your target role'}: {VERB_BANK.get(family, 'Built, Led, Delivered, Improved, Resolved, Trained')}.",
            count=sum(repeated.values()))
    if audit.overlong_bullets_count:
        add("medium", "Cut long bullets down to one idea",
            f"{_n(audit.overlong_bullets_count, 'bullet')} {_verb(audit.overlong_bullets_count, 'runs', 'run')} long enough to wrap past two lines.",
            "Long bullets get skimmed, and the result at the end is the part that gets missed.",
            "Keep one achievement per bullet, about 25 to 30 words. Move the result earlier if it is buried.",
            _first_rec(recs, "condense"), count=audit.overlong_bullets_count)
    if skills.unsupported_skills:
        add("high" if len(skills.unsupported_skills) >= 5 else "medium", "Prove or prune your skills list",
            f"{_n(len(skills.unsupported_skills), 'listed skill')} {_verb(len(skills.unsupported_skills), 'is', 'are')} not shown in any role or project: {', '.join(skills.unsupported_skills[:6])}.",
            "A long unsupported list reads as keyword stuffing and invites interview questions you may not be able to answer.",
            "Keep skills you can show or discuss in depth. For each one you keep, make sure a bullet shows it in use.",
            count=len(skills.unsupported_skills))
    move = _first_rec(recs, "move")
    if move:
        add("medium", "Put your strongest section first", move.why_stronger or "Your strongest evidence is not where the reader looks first.",
            "Recruiters spend most attention on the top third of page one.", move.suggested_text or "Order sections by strength of evidence for the target role.")
    essentials = [c for c in primary.competencies if c.essential] if primary else []
    thin = [c for c in essentials if c.coverage != "in_experience" or c.depth == "mentioned"]
    if primary and thin:
        add("high" if 2 * len(thin) > len(essentials) else "medium", f"Write for {primary.title}",
            f"{len(thin)} of {len(essentials)} essential competencies for this role are missing, only listed, or described as duties: {_join([c.label.lower() for c in thin][:3])}.",
            primary.benchmark,
            f"{primary.writing_focus} Put the bullets that evidence {_join([c.label.lower() for c in essentials][:3])} first in each role.",
            count=len(thin))
    return ups


def _action(actions: List[DevelopmentAction], **fields) -> None:
    actions.append(DevelopmentAction(action_id=f"dev_{len(actions) + 1}", **fields))


def build_elevation_plan(
    extracted: ExtractedCV,
    audit: DeterministicCVAudit,
    skills: SkillsCredibilityAudit,
    context: AnalysisContext,
    targets: Optional[RoleTargetingResult],
    recommendations: List[RecommendationItem],
) -> ElevationPlan:
    primary = primary_target(targets)
    profile = PROFILES_BY_ID.get(primary.role_id) if primary else None
    writing = _writing_upgrades(extracted, audit, skills, context, primary, recommendations)
    roles = [primary.title] if primary else []
    tech = bool(primary and primary.family in CODE_FAMILIES)
    section_types = {s.normalized_type for s in extracted.sections}

    add_now: List[DevelopmentAction] = []
    contact = extracted.contact
    if tech and not contact.github and not contact.portfolio_links:
        _action(add_now, kind="add_now_if_true", title="Add your GitHub or portfolio link",
                detail="Recruiters for technical roles often check code before inviting you to interview. Pin the repositories you would be happy to discuss.",
                why="A link lets the reader verify your project claims in seconds.", timeframe="This week", effort="Low",
                for_roles=roles, rubric_effect="Strengthens Skills credibility and Projects evidence.", cv_line_once_done="github.com/[username]")
    if not contact.linkedin:
        _action(add_now, kind="add_now_if_true", title="Add your LinkedIn URL",
                detail="Only if the profile matches this CV. Mismatched dates or titles are a common red flag.",
                why="Most recruiters cross-check LinkedIn before a first call.", timeframe="This week", effort="Low",
                for_roles=roles, rubric_effect="Completes the contact header (Structure).", cv_line_once_done="linkedin.com/in/[your-name]")
    if primary and profile:
        comps = {c.key: c for c in profile.competencies}
        where = {"skills_list_only": "skills list", "summary_only": "summary, education or a heading"}
        for ev in [c for c in primary.competencies if c.coverage in where][:3]:
            _action(add_now, kind="add_now_if_true", title=f"Show {ev.label.lower()} in a bullet, if you have used it",
                    detail=f"'{ev.evidence_quote}' appears only in your {where[ev.coverage]}. If you have used it at work, in study or in a project, add a bullet showing how. If not, remove it.",
                    why="Listed-but-unshown skills earn little credit and invite awkward interview questions.", timeframe="This week", effort="Low",
                    for_roles=roles, rubric_effect=f"Moves {ev.label.lower()} from listed to evidenced (Skills credibility, Role relevance).",
                    cv_line_once_done=comps[ev.key].cv_line if ev.key in comps else "")
    if tech and "projects" not in section_types:
        _action(add_now, kind="add_now_if_true", title="Add a Projects section, if you have built anything",
                detail="Coursework, hackathons and personal projects all count. Give what it does, your part, the tools, and a link.",
                why="Projects are often the only evidence of skills your job titles don't show.", timeframe="This week", effort="Low",
                for_roles=roles, rubric_effect="Adds Experience and project quality evidence.", cv_line_once_done="[Project name]: [what it does], built with [tools]. [link]")
    if "certifications" not in section_types:
        _action(add_now, kind="add_now_if_true", title="List relevant courses or certificates you have completed",
                detail="Completed ones only, with the year. A course still in progress can say 'expected [month year]'.",
                why="Shows you are investing in the target field, especially for early-career and pivot applications.", timeframe="This week", effort="Low",
                for_roles=roles, rubric_effect="Minor support for Skills credibility.", cv_line_once_done="[Certificate name], [issuer], [year]")

    begin: List[DevelopmentAction] = []
    seen = set()
    candidates = targets.candidates if targets else []
    adjacent = [c for c in candidates if not c.is_primary and c.fit_percentage >= 40]
    other_budget = 3
    for target in ([primary] if primary else []) + adjacent:
        target_profile = PROFILES_BY_ID.get(target.role_id)
        limit = 4 if target is primary else min(2, other_budget)
        if not target_profile or limit <= 0:
            continue
        comps = {c.key: c for c in target_profile.competencies}
        gaps = sorted((c for c in target.competencies if c.coverage == "missing" or (c.essential and c.coverage == "skills_list_only")),
                      key=lambda c: (not c.essential, c.coverage != "missing"))
        picked = [g for g in gaps if g.key not in seen][:limit]
        if target is not primary:
            other_budget -= len(picked)
        for ev in picked:
            seen.add(ev.key)
            comp = comps[ev.key]
            _action(begin, kind="build_evidence" if comp.effort != "Low" else "start_doing", title=comp.action, detail=comp.action_detail,
                    why=f"{'Essential' if ev.essential else 'Useful'} for {target.title}; currently {'missing from' if ev.coverage == 'missing' else 'only listed in'} your CV.",
                    timeframe=comp.timeframe, effort=comp.effort, for_roles=[target.title],
                    rubric_effect=f"Gives you evidence of {ev.label.lower()} (Role relevance, Skills credibility).", cv_line_once_done=comp.cv_line)
    proven = audit.tier_counts.get("tier_3_concrete_evidence", 0) + audit.tier_counts.get("tier_4_verified_outcome", 0)
    if proven < max(2, 0.6 * max(1, audit.total_bullets)):
        _action(begin, kind="start_doing", title="Keep a weekly record of results",
                detail="Every Friday, note what you delivered or handled, how many or how much, and what changed. Ask your manager for figures you can't see yourself.",
                why="Most of the rewrites above are blocked on numbers you don't have yet. Results you never record can't go on a CV.",
                timeframe="This week", effort="Low", for_roles=roles, rubric_effect="Feeds the Impact category directly.",
                cv_line_once_done="[Action] [what] for [who], [result with a real figure].")
    stage = STAGE_ACTIONS.get(context.career_level)
    if stage:
        title, detail, timeframe, effort, line = stage
        _action(begin, kind="build_evidence", title=title, detail=detail, why="The step that most often separates shortlisted CVs at your career stage.",
                timeframe=timeframe, effort=effort, for_roles=roles, rubric_effect="Adds Experience and Impact evidence.", cv_line_once_done=line)
    if profile and profile.credential:
        _action(begin, kind="credential", title=f"Optional: {profile.credential}",
                detail="Useful as a signal of intent, especially for a career change. A project or work result showing the same skill counts for more with most recruiters.",
                why="Some screeners filter on certificates for this role family.", timeframe="Next 90 days", effort="Medium",
                for_roles=roles, rubric_effect="Small Skills credibility gain; no substitute for evidence.", cv_line_once_done="[Certificate name], [issuer], [year]")
    begin.sort(key=lambda a: TIMEFRAME_ORDER[a.timeframe])

    first_gap = next((c.label.lower() for c in (primary.competencies if primary else []) if c.essential and c.coverage != "in_experience"), "")
    if writing and primary and first_gap:
        headline = f"Start with \"{writing[0].title.lower()}\". For {primary.title}, your biggest evidence gap is {first_gap}."
    elif writing and primary:
        headline = f"Your evidence already covers {primary.title}; the gains now come from writing. Start with \"{writing[0].title.lower()}\"."
    else:
        headline = "Few writing issues were detected; focus on building fresh evidence for your target roles."
    return ElevationPlan(headline=headline, writing_upgrades=writing, add_now_if_true=add_now, actions_to_begin=begin, honesty_note=HONESTY_NOTE)
