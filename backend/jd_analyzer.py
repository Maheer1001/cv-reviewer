import re
from typing import List, Tuple

from backend.it_vocabulary import CANONICAL_SKILLS
from backend.schemas import (
    AnalysisContext,
    ExtractedCV,
    JDEvidenceStatus,
    JDComparisonResult,
    JDRequirement,
)


DESIRABLE_SIGNAL_REGEX = re.compile(
    r"\b(?:desirable|nice\s+to\s+have|preferred|bonus|advantageous|ideally|plus|optional)\b",
    re.I,
)

BEHAVIOURAL_SIGNAL_REGEX = re.compile(
    r"\b(?:collaborat|communicat|mentor|stakeholder|agile|cross[\s-]?functional|leadership|ownership|autonom|problem[\s-]?solving)\b",
    re.I,
)

QUALIFICATION_SIGNAL_REGEX = re.compile(
    r"\b(?:degree|bsc|msc|phd|bachelor|master|computer\s+science|years?\b|experience\s+in|certified|certification)\b",
    re.I,
)

DOMAIN_SIGNAL_REGEX = re.compile(
    r"\b(?:fintech|payments|healthcare|e[\s-]?commerce|saas|distributed\s+systems|high[\s-]?throughput|regulated|cloud[\s-]?native|security|compliance)\b",
    re.I,
)


def analyze_job_description_alignment(
    extracted_cv: ExtractedCV,
    context: AnalysisContext,
) -> JDComparisonResult:
    """
    Parse the supplied Job Description into structured Essential and Desirable requirements
    and map each requirement against verified evidence in the CV.
    """
    jd_text = (context.job_description or "").strip()
    if not jd_text:
        return JDComparisonResult(
            provided=False,
            job_title_analyzed=context.target_job_title or "Unspecified Role",
            alignment_percentage=0,
            application_verdict=(
                "No job description was supplied. Role-specific suitability cannot be assessed reliably "
                "without the target vacancy's essential and desirable criteria."
            ),
        )

    requirements: List[JDRequirement] = []
    req_idx = 0

    # 1. Extract explicit skill requirements from JD and check against CV sections
    cv_Lower = extracted_cv.raw_text.lower()
    exp_proj_lines: List[Tuple[str, str]] = []
    skills_only_lines: List[str] = []
    project_lines: List[str] = []

    for sec in extracted_cv.sections:
        for item in sec.items:
            if sec.normalized_type in ("experience", "projects"):
                exp_proj_lines.append((sec.title, item.text))
            if sec.normalized_type == "projects":
                project_lines.append(item.text)
        if sec.normalized_type == "skills":
            skills_only_lines.extend(sec.raw_lines)

    skills_blob = "\n".join(skills_only_lines)

    # Split JD into clauses/lines to identify whether a skill appears in a "Desirable / Nice to have" block
    jd_lines = [ln.strip(" •●▪-*") for ln in jd_text.splitlines() if ln.strip()]
    in_desirable_section = False
    line_importance: List[Tuple[str, str]] = []
    for ln in jd_lines:
        if re.match(r"^(?:desirable|nice\s+to\s+have|preferred|bonus\s+points)[:\s]*$", ln, re.I):
            in_desirable_section = True
            continue
        if re.match(r"^(?:essential|requirements|what\s+you'?ll\s+need|must\s+have|responsibilities)[:\s]*$", ln, re.I):
            in_desirable_section = False
            continue
        imp = "Desirable" if (in_desirable_section or DESIRABLE_SIGNAL_REGEX.search(ln)) else "Essential"
        line_importance.append((ln, imp))

    matched_canonical_skills = set()
    buried_experience: List[str] = []
    skills_to_highlight: List[str] = []
    matching_projects: List[str] = []
    missing_info_prompts: List[str] = []
    genuine_gaps: List[str] = []

    for skill_name, (_, pat) in CANONICAL_SKILLS.items():
        if not pat.search(jd_text):
            continue
        matched_canonical_skills.add(skill_name)
        # Check if desirable or essential in JD
        imp = "Essential"
        for ln, l_imp in line_importance:
            if pat.search(ln):
                imp = l_imp
                break

        exp_matches = [f"[{sec_t}] {txt}" for sec_t, txt in exp_proj_lines if pat.search(txt)]
        proj_matches = [txt for txt in project_lines if pat.search(txt)]
        in_skills = bool(pat.search(skills_blob))

        req_idx += 1
        if exp_matches:
            status: JDEvidenceStatus = "clearly_demonstrated"
            evidence_str = exp_matches[0][:160]
            note = f"{skill_name} is substantiated by concrete work/project evidence."
            advice = f"Keep {skill_name} prominent; ensure the outcome of this work is quantified where possible."
            if not in_skills:
                buried_experience.append(
                    f"{skill_name} is demonstrated in {exp_matches[0][:90]}..., but omitted from your Skills section."
                )
                skills_to_highlight.append(skill_name)
            if proj_matches:
                matching_projects.append(f"{skill_name} evidenced in project bullet: \"{proj_matches[0][:100]}\"")
        elif in_skills or pat.search(cv_Lower):
            status = "partially_demonstrated"
            evidence_str = f"Listed in Skills/Summary ('{skill_name}'), but zero Experience or Project bullets demonstrate it in action."
            note = f"Recruiters treat a bare mention of {skill_name} in a skills list as unverified until proven in a project or role."
            advice = f"Add a specific bullet in Work Experience or Projects showing what you built, tested, or solved using {skill_name}."
            skills_to_highlight.append(skill_name)
            missing_info_prompts.append(
                f"Where have you used {skill_name} in practice, and what did you build or solve with it?"
            )
        else:
            status = "not_evidenced"
            evidence_str = f"Not evidenced anywhere in the uploaded CV."
            note = (
                f"'{skill_name}' ({imp}) is not mentioned in your CV. Note: 'Not evidenced' means the document "
                "provides no evidence of it, not proof that you lack the ability."
            )
            advice = (
                f"If you have genuine experience with {skill_name}, add a substantiated bullet demonstrating it. "
                "Do not insert the keyword if you cannot defend it in a technical interview."
            )
            if imp == "Essential":
                genuine_gaps.append(f"Essential requirement '{skill_name}' is not evidenced in the CV.")
            else:
                missing_info_prompts.append(f"Do you have any project or commercial exposure to {skill_name} (Desirable)?")

        requirements.append(
            JDRequirement(
                req_id=f"jd_req_{req_idx}",
                category="Required Technical / Professional Skill",
                importance=imp,  # type: ignore[arg-type]
                requirement_text=f"Demonstrated proficiency in {skill_name}",
                status=status,
                cv_evidence=evidence_str,
                recruiter_note=note,
                targeted_advice=advice,
            )
        )

    # 2. Extract non-skill qualification, responsibility, domain, and behavioural lines from the JD
    for ln, imp in line_importance:
        if len(ln.split()) < 4 or len(ln) > 220:
            continue
        # Skip if line only mentions canonical skills already covered and has < 8 words
        if any(pat.search(ln) for _, pat in CANONICAL_SKILLS.values()) and len(ln.split()) < 9:
            continue

        if QUALIFICATION_SIGNAL_REGEX.search(ln):
            cat = (
                "Essential Qualification / Experience"
                if imp == "Essential"
                else "Desirable Qualification / Experience"
            )
        elif DOMAIN_SIGNAL_REGEX.search(ln):
            cat = "Industry / Domain Knowledge"
        elif BEHAVIOURAL_SIGNAL_REGEX.search(ln):
            cat = "Behaviour / Competency"
        else:
            cat = "Core Responsibility"

        # Extract meaningful content keywords from the requirement line
        stop = {
            "with", "from", "that", "this", "have", "will", "your", "work", "working", "team",
            "experience", "ability", "strong", "good", "knowledge", "understanding", "role",
            "candidate", "must", "should", "looking", "ideal", "essential", "desirable", "preferred",
        }
        keywords = [
            w.lower()
            for w in re.findall(r"[a-zA-Z]{4,}", ln)
            if w.lower() not in stop
        ]
        if not keywords:
            continue

        # Search CV bullets for overlap
        best_line = ""
        best_overlap = 0
        for sec_t, b_txt in exp_proj_lines:
            b_low = b_txt.lower()
            overlap = sum(1 for kw in set(keywords) if kw in b_low)
            if overlap > best_overlap:
                best_overlap = overlap
                best_line = f"[{sec_t}] {b_txt}"

        overlap_ratio = best_overlap / max(1, len(set(keywords)))
        req_idx += 1
        if overlap_ratio >= 0.45 or best_overlap >= 3:
            status = "clearly_demonstrated"
            ev = best_line[:160]
            note = "Substantiated by matching experience/project evidence in the CV."
            adv = "Ensure this evidence appears in the top half of the CV for immediate recruiter visibility."
        elif overlap_ratio >= 0.25 or best_overlap >= 2:
            status = "partially_demonstrated"
            ev = best_line[:160] if best_line else "Related terminology appears in the CV without explicit depth."
            note = "Partially evidenced, but the specific scope or outcome sought by the job description is understated."
            adv = f"Refine '{best_line[:60]}...' to directly address: {ln[:90]}."
            buried_experience.append(f"Partial match for '{ln[:70]}' found in {best_line[:80]} — strengthen the link.")
        else:
            status = "not_evidenced"
            ev = "No direct supporting passage found in the CV."
            note = "Not currently evidenced in the CV text."
            adv = "If you have fulfilled this requirement in a past role or project, add a concrete example; otherwise treat as an interview gap to prepare for."
            if imp == "Essential" and len(genuine_gaps) < 6:
                genuine_gaps.append(f"Unaddressed essential requirement: \"{ln[:100]}\"")

        requirements.append(
            JDRequirement(
                req_id=f"jd_req_{req_idx}",
                category=cat,  # type: ignore[arg-type]
                importance=imp,  # type: ignore[arg-type]
                requirement_text=ln[:150],
                status=status,
                cv_evidence=ev,
                recruiter_note=note,
                targeted_advice=adv,
            )
        )
        if len(requirements) >= 14:
            break

    # Compute weighted alignment percentage (Essential weighted 2x Desirable)
    total_weight = 0.0
    achieved_weight = 0.0
    for r in requirements:
        w = 2.0 if r.importance == "Essential" else 1.0
        total_weight += w
        if r.status == "clearly_demonstrated":
            achieved_weight += w
        elif r.status == "partially_demonstrated":
            achieved_weight += w * 0.5

    alignment_pct = int(round((achieved_weight / max(1.0, total_weight)) * 100)) if requirements else 50

    clear_n = sum(1 for r in requirements if r.status == "clearly_demonstrated")
    partial_n = sum(1 for r in requirements if r.status == "partially_demonstrated")
    missing_n = sum(1 for r in requirements if r.status == "not_evidenced")

    verdict = (
        f"Against the supplied job description ({len(requirements)} requirements extracted: "
        f"{clear_n} clearly demonstrated, {partial_n} partially demonstrated, {missing_n} not evidenced), "
        f"your CV achieves an evidence alignment of {alignment_pct}%. "
    )
    if alignment_pct >= 75:
        verdict += "You demonstrate strong core alignment with the vacancy, though tightening partial evidence will materially strengthen your shortlist case."
    elif alignment_pct >= 50:
        verdict += (
            "You have plausible foundational fit, but several essential requirements are either only listed as bare keywords "
            "or buried without concrete outcomes. A demanding recruiter may hesitate without targeted revisions."
        )
    else:
        verdict += (
            "Significant evidence gaps exist between the current CV and the vacancy's essential criteria. "
            "Unless you have omitted relevant experience that can be added truthfully, this application is at high risk of rejection."
        )

    return JDComparisonResult(
        provided=True,
        job_title_analyzed=context.target_job_title or "Supplied Vacancy",
        alignment_percentage=alignment_pct,
        requirements=requirements,
        buried_or_understated_experience=buried_experience[:5],
        skills_to_highlight_clearer=skills_to_highlight[:6],
        relevant_projects_matching_jd=matching_projects[:4],
        missing_info_candidate_could_supply=missing_info_prompts[:5],
        genuine_experience_gaps=genuine_gaps[:5],
        application_verdict=verdict,
    )
