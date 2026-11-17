from typing import Dict, List, Literal, Optional
from pydantic import BaseModel, Field


CareerLevel = Literal[
    "student_graduate",
    "junior",
    "mid_level",
    "senior_lead",
    "career_changer",
    "executive",
]

RecommendationAction = Literal[
    "keep",
    "rewrite",
    "cut",
    "add",
    "move",
    "condense",
    "verify",
]

RecommendationStatus = Literal[
    "pending",
    "accepted",
    "rejected",
    "unresolved",
]

PriorityLevel = Literal["critical", "high", "medium", "low"]

EvidenceTier = Literal[
    "tier_0_generic",
    "tier_1_responsibility_only",
    "tier_2_technical_detail",
    "tier_3_concrete_evidence",
    "tier_4_verified_outcome",
]

JDEvidenceStatus = Literal[
    "clearly_demonstrated",
    "partially_demonstrated",
    "not_evidenced",
    "not_applicable",
]

QuestionResolutionType = Literal[
    "unanswered",
    "answered",
    "skipped",
    "dont_know",
    "confidential",
    "use_existing",
]


class RubricWeights(BaseModel):
    relevance_alignment: int = Field(default=20, ge=0, le=100)
    impact_achievements: int = Field(default=20, ge=0, le=100)
    experience_project_quality: int = Field(default=20, ge=0, le=100)
    skills_credibility: int = Field(default=15, ge=0, le=100)
    writing_clarity: int = Field(default=10, ge=0, le=100)
    structure_readability: int = Field(default=10, ge=0, le=100)
    ats_compatibility: int = Field(default=5, ge=0, le=100)

    def total(self) -> int:
        return (
            self.relevance_alignment
            + self.impact_achievements
            + self.experience_project_quality
            + self.skills_credibility
            + self.writing_clarity
            + self.structure_readability
            + self.ats_compatibility
        )

    def normalized(self) -> "RubricWeights":
        t = self.total()
        if t == 100:
            return self
        if t <= 0:
            return RubricWeights()
        keys = [
            "relevance_alignment",
            "impact_achievements",
            "experience_project_quality",
            "skills_credibility",
            "writing_clarity",
            "structure_readability",
            "ats_compatibility",
        ]
        raw = {k: getattr(self, k) for k in keys}
        scaled = {k: int(round(v * 100.0 / t)) for k, v in raw.items()}
        diff = 100 - sum(scaled.values())
        if diff != 0:
            max_key = max(scaled, key=lambda k: scaled[k])
            scaled[max_key] += diff
        return RubricWeights(**scaled)


class ContactDetails(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    linkedin: Optional[str] = None
    github: Optional[str] = None
    portfolio_links: List[str] = Field(default_factory=list)
    found_in_header_or_footer: bool = False
    missing_critical_fields: List[str] = Field(default_factory=list)


class ExtractedBullet(BaseModel):
    bullet_id: str
    section_name: str
    entry_title: Optional[str] = None
    text: str
    is_bullet: bool = True
    line_index: int = 0


class ExtractedSection(BaseModel):
    section_id: str
    title: str
    normalized_type: Literal[
        "contact",
        "summary",
        "experience",
        "projects",
        "education",
        "skills",
        "certifications",
        "additional",
    ]
    raw_lines: List[str] = Field(default_factory=list)
    items: List[ExtractedBullet] = Field(default_factory=list)


class ATSDetectedIssue(BaseModel):
    issue_id: str
    severity: Literal["high", "medium", "low", "info"]
    issue_type: Literal["verified_document_issue", "general_best_practice"]
    title: str
    description: str
    evidence: str
    remediation: str


class DocumentDiagnostics(BaseModel):
    filename: str
    file_format: Literal["pdf", "docx", "txt"]
    file_size_bytes: int
    page_count: int = 1
    word_count: int = 0
    char_count: int = 0
    bullet_count: int = 0
    section_count: int = 0
    has_tables: bool = False
    table_count: int = 0
    has_multi_column_layout: bool = False
    has_text_boxes_or_shapes: bool = False
    has_header_footer_content: bool = False
    header_footer_text: List[str] = Field(default_factory=list)
    links_extracted: List[str] = Field(default_factory=list)
    extraction_complete: bool = True
    extraction_warnings: List[str] = Field(default_factory=list)
    reading_order_anomalies: List[str] = Field(default_factory=list)
    standard_headings_used: bool = True
    ambiguous_headings: List[str] = Field(default_factory=list)
    ats_issues: List[ATSDetectedIssue] = Field(default_factory=list)


class BulletDeterministicAudit(BaseModel):
    bullet_id: str
    section_name: str
    entry_title: Optional[str] = None
    text: str
    word_count: int
    sentence_count: int
    opening_word: str
    evidence_tier: EvidenceTier
    evidence_tier_label: str
    evidence_tier_reason: str
    has_concrete_tech_or_method: bool = False
    has_verified_metric_or_scope: bool = False
    has_unanchored_claim: bool = False
    unanchored_claim_reason: Optional[str] = None
    buzzwords_found: List[str] = Field(default_factory=list)
    weak_verb_prefix: Optional[str] = None
    is_too_short: bool = False
    is_overlong: bool = False
    duplicate_of_bullet_id: Optional[str] = None


class DeterministicCVAudit(BaseModel):
    total_words: int = 0
    total_bullets: int = 0
    avg_bullet_words: float = 0.0
    short_bullets_count: int = 0
    overlong_bullets_count: int = 0
    tier_counts: Dict[str, int] = Field(default_factory=dict)
    repeated_opening_verbs: Dict[str, int] = Field(default_factory=dict)
    duplicate_bullet_pairs: List[Dict[str, str]] = Field(default_factory=list)
    repeated_phrases: List[str] = Field(default_factory=list)
    buzzwords_detected: List[str] = Field(default_factory=list)
    unanchored_claims_detected: List[Dict[str, str]] = Field(default_factory=list)
    bullet_audits: List[BulletDeterministicAudit] = Field(default_factory=list)


class ExtractedCV(BaseModel):
    raw_text: str
    contact: ContactDetails
    sections: List[ExtractedSection] = Field(default_factory=list)
    all_bullets: List[ExtractedBullet] = Field(default_factory=list)
    diagnostics: DocumentDiagnostics
    deterministic_audit: Optional[DeterministicCVAudit] = None


class AnalysisContext(BaseModel):
    target_job_title: str = ""
    target_industry: str = ""
    career_level: CareerLevel = "mid_level"
    job_description: str = ""
    language: str = "en-GB"
    weights: RubricWeights = Field(default_factory=RubricWeights)
    use_llm: bool = True
    career_level_source: Literal["user", "auto", "inferred"] = "user"
    career_level_reason: str = ""
    pinned_role_id: str = ""


class ScoreDeductionItem(BaseModel):
    reason: str
    points_impact: int  # negative for deduction, positive for credit
    source: Literal["deterministic_rule", "semantic_ai_judgement"]
    evidence_ref: str


class CategoryScore(BaseModel):
    category_key: str
    category_name: str
    raw_rating_out_of_100: int = Field(ge=0, le=100)
    deterministic_subscore: int = Field(default=50, ge=0, le=100)
    semantic_subscore: Optional[int] = None
    weight: int = Field(ge=0, le=100)
    achieved_points: float
    max_points: float
    scoring_criteria: str
    deductions_and_credits: List[ScoreDeductionItem] = Field(default_factory=list)
    supporting_evidence: List[str] = Field(default_factory=list)
    main_weaknesses: List[str] = Field(default_factory=list)
    improvement_actions: List[str] = Field(default_factory=list)
    uncertainty_note: Optional[str] = None


class ThreePillarAssessment(BaseModel):
    general_cv_quality_score: int = Field(ge=0, le=100)
    general_cv_quality_verdict: str
    role_suitability_assessed: bool
    role_suitability_score: Optional[int] = None
    role_suitability_verdict: str
    application_competitiveness_rating: Literal[
        "Highly Competitive",
        "Moderately Competitive",
        "Borderline / At Risk of Rejection",
        "Uncompetitive in Current Form",
        "Insufficient Role Context",
    ]
    application_competitiveness_verdict: str


class DimensionEvaluation(BaseModel):
    dimension_code: str  # A through J
    dimension_title: str
    verdict_badge: Literal["Strong", "Adequate", "Weak", "Critical Defect"]
    recruiter_assessment: str
    evidence_quotes: List[str] = Field(default_factory=list)
    specific_defects: List[str] = Field(default_factory=list)
    recruiter_inference: str


class SkillsCredibilityAudit(BaseModel):
    claimed_skills: List[str] = Field(default_factory=list)
    evidenced_skills: List[Dict[str, str]] = Field(default_factory=list)
    unsupported_skills: List[str] = Field(default_factory=list)
    omitted_demonstrated_skills: List[str] = Field(default_factory=list)
    overloaded_or_unsubstantiated_levels: List[str] = Field(default_factory=list)
    recommended_categories: Dict[str, List[str]] = Field(default_factory=dict)
    recruiter_commentary: str = ""


class TopWeakness(BaseModel):
    rank: int = Field(ge=1, le=5)
    problem_title: str
    exact_problem: str
    where_it_appears: str
    recruiter_impact: str
    how_to_address: str
    expected_impact: str


class SectionReview(BaseModel):
    section_id: str
    section_title: str
    normalized_type: str
    rating: Literal["Strong", "Mixed", "Weak", "Missing / Critical"]
    score_out_of_10: int = Field(ge=0, le=10)
    summary_verdict: str
    strengths: List[str] = Field(default_factory=list)
    weaknesses: List[str] = Field(default_factory=list)
    key_recommendations: List[str] = Field(default_factory=list)


class PrioritisedAction(BaseModel):
    step_number: int
    priority: PriorityLevel
    action_title: str
    rationale: str
    target_area: str
    expected_score_lift: str


class RecommendationItem(BaseModel):
    rec_id: str
    action: RecommendationAction
    priority: PriorityLevel
    section_name: str
    bullet_id: Optional[str] = None
    original_text: str = ""
    suggested_text: str = ""
    alternative_text: Optional[str] = None
    what_changed: str = ""
    why_stronger: str = ""
    recruiter_benefit: str = ""
    missing_info_required: Optional[str] = None
    # Explicit evidence & rubric linkage (Requirement 3)
    evidence_type: Literal["verified_quote", "explicit_omission", "structural_observation"] = "verified_quote"
    rubric_criteria_affected: List[str] = Field(default_factory=list)
    evidence_reasoning: str = ""
    source_stage: Literal["deterministic", "semantic_ai", "hybrid"] = "hybrid"
    # Cut-specific fields
    cut_handling: Optional[Literal["remove_entirely", "shorten", "replace"]] = None
    value_lost_if_removed: Optional[str] = None
    space_reallocation_advice: Optional[str] = None
    # Add-specific fields
    is_essential: bool = True
    question_to_answer: Optional[str] = None
    # Move/Condense fields
    target_destination: Optional[str] = None
    # State management
    status: RecommendationStatus = "pending"
    user_edited_text: Optional[str] = None
    linked_question_id: Optional[str] = None
    verified_in_cv: bool = True


class FollowUpQuestion(BaseModel):
    question_id: str
    linked_rec_id: Optional[str] = None
    bullet_id: Optional[str] = None
    section_name: str
    original_excerpt: str
    category: str
    priority: PriorityLevel
    primary_question: str
    sub_questions: List[str] = Field(default_factory=list)
    why_recruiter_asks: str
    resolution_type: QuestionResolutionType = "unanswered"
    user_answer: str = ""
    synthesized_rewrite: Optional[str] = None


class JDRequirement(BaseModel):
    req_id: str
    category: Literal[
        "Essential Qualification / Experience",
        "Desirable Qualification / Experience",
        "Required Technical / Professional Skill",
        "Core Responsibility",
        "Industry / Domain Knowledge",
        "Behaviour / Competency",
    ]
    importance: Literal["Essential", "Desirable"]
    requirement_text: str
    status: JDEvidenceStatus
    cv_evidence: str
    recruiter_note: str
    targeted_advice: str


class JDComparisonResult(BaseModel):
    provided: bool = False
    job_title_analyzed: str = ""
    alignment_percentage: int = 0
    requirements: List[JDRequirement] = Field(default_factory=list)
    buried_or_understated_experience: List[str] = Field(default_factory=list)
    skills_to_highlight_clearer: List[str] = Field(default_factory=list)
    relevant_projects_matching_jd: List[str] = Field(default_factory=list)
    missing_info_candidate_could_supply: List[str] = Field(default_factory=list)
    genuine_experience_gaps: List[str] = Field(default_factory=list)
    application_verdict: str = ""


class OverallVerdict(BaseModel):
    overall_score: float
    blunt_recruiter_verdict: str
    career_stage_calibration_note: str
    strongest_aspect: str
    biggest_weakness: str
    competitiveness_summary: str
    important_limitations_and_uncertainties: List[str] = Field(default_factory=list)
    analysis_engine_used: str
    model_identifier: str


class RoleCompetencyEvidence(BaseModel):
    key: str
    label: str
    essential: bool
    coverage: Literal["in_experience", "summary_only", "skills_list_only", "missing"]
    depth: Literal["proven", "described", "mentioned", "none"]
    evidence_quote: str = ""
    bullet_id: Optional[str] = None


class RoleTarget(BaseModel):
    role_id: str
    title: str
    family: str
    fit_percentage: int = Field(ge=0, le=100)
    evidence_strength: int = Field(ge=0, le=100)
    confidence: Literal["high", "medium", "low"]
    readiness: str
    is_user_target: bool = False
    is_primary: bool = False
    why_inferred: List[str] = Field(default_factory=list)
    competencies: List[RoleCompetencyEvidence] = Field(default_factory=list)
    benchmark: str = ""
    writing_focus: str = ""
    top_gaps: List[str] = Field(default_factory=list)
    next_steps: List[str] = Field(default_factory=list)


class RoleTargetingResult(BaseModel):
    role_was_specified: bool
    specified_title: str = ""
    specified_title_matched_profile: bool = False
    primary_role_id: str = ""
    primary_title: str = ""
    candidates: List[RoleTarget] = Field(default_factory=list)
    semantic_suggestions: List[str] = Field(default_factory=list)
    career_level_used: str
    career_level_source: str
    career_level_reason: str = ""
    method_note: str = ""


class WritingUpgrade(BaseModel):
    upgrade_id: str
    priority: PriorityLevel
    title: str
    problem: str
    why_it_matters: str
    how_to_fix: str
    example_before: str = ""
    example_after: str = ""
    affected_count: int = 0


class DevelopmentAction(BaseModel):
    action_id: str
    kind: Literal["add_now_if_true", "start_doing", "build_evidence", "credential"]
    title: str
    detail: str
    why: str
    timeframe: Literal["This week", "Next 30 days", "Next 90 days"]
    effort: Literal["Low", "Medium", "High"]
    for_roles: List[str] = Field(default_factory=list)
    rubric_effect: str = ""
    cv_line_once_done: str = ""


class ElevationPlan(BaseModel):
    headline: str
    writing_upgrades: List[WritingUpgrade] = Field(default_factory=list)
    add_now_if_true: List[DevelopmentAction] = Field(default_factory=list)
    actions_to_begin: List[DevelopmentAction] = Field(default_factory=list)
    honesty_note: str = ""


class CVAnalysisReport(BaseModel):
    verdict: OverallVerdict
    three_pillars: ThreePillarAssessment
    weights_used: RubricWeights
    deterministic_audit: DeterministicCVAudit
    category_scores: List[CategoryScore] = Field(default_factory=list)
    top_weaknesses: List[TopWeakness] = Field(default_factory=list)
    section_reviews: List[SectionReview] = Field(default_factory=list)
    prioritised_action_plan: List[PrioritisedAction] = Field(default_factory=list)
    dimensions: List[DimensionEvaluation] = Field(default_factory=list)
    skills_audit: SkillsCredibilityAudit
    recommendations: List[RecommendationItem] = Field(default_factory=list)
    follow_up_questions: List[FollowUpQuestion] = Field(default_factory=list)
    jd_comparison: JDComparisonResult
    role_targets: Optional[RoleTargetingResult] = None
    elevation_plan: Optional[ElevationPlan] = None
    validation_notes: List[str] = Field(default_factory=list)


class ChangeHistoryEvent(BaseModel):
    event_id: str
    timestamp: str
    rec_id: Optional[str] = None
    action_taken: str
    section_name: str
    before_text: str
    after_text: str


class WorkingEntry(BaseModel):
    item_id: str
    original_text: str
    current_text: str
    is_bullet: bool = True
    is_deleted: bool = False
    is_added: bool = False
    modified_by_rec_id: Optional[str] = None
    has_unverified_placeholder: bool = False


class WorkingSection(BaseModel):
    section_id: str
    title: str
    normalized_type: str
    entries: List[WorkingEntry] = Field(default_factory=list)


class WorkingCV(BaseModel):
    contact: ContactDetails
    sections: List[WorkingSection] = Field(default_factory=list)
    original_section_ids: List[str] = Field(default_factory=list)
    unresolved_placeholders: List[str] = Field(default_factory=list)
    change_history: List[ChangeHistoryEvent] = Field(default_factory=list)
    accepted_count: int = 0
    rejected_count: int = 0
    pending_count: int = 0
    unresolved_count: int = 0


class CategoryDelta(BaseModel):
    category_key: str
    category_name: str
    original_points: float
    revised_points: float
    max_points: float
    delta_points: float
    original_raw: int
    revised_raw: int
    evidence_of_change: str


class ReassessmentComparison(BaseModel):
    original_score: float
    revised_score: float
    score_delta: float
    reassessment_verdict: str
    category_deltas: List[CategoryDelta] = Field(default_factory=list)
    improvements_verified: List[str] = Field(default_factory=list)
    remaining_weaknesses: List[str] = Field(default_factory=list)
    rejected_worth_reconsidering: List[str] = Field(default_factory=list)
    unresolved_questions_or_missing_info: List[str] = Field(default_factory=list)
    new_problems_introduced: List[str] = Field(default_factory=list)
    revised_report: CVAnalysisReport


class SessionState(BaseModel):
    session_id: str
    created_at: str
    context: AnalysisContext
    extracted_cv: ExtractedCV
    initial_report: CVAnalysisReport
    working_cv: WorkingCV
    latest_reassessment: Optional[ReassessmentComparison] = None
