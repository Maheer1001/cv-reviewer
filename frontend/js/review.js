/* Score breakdown and section-by-section review tabs. */
const JD_STATUS = {
  clearly_demonstrated: ["Clearly evidenced", "badge-good"],
  partially_demonstrated: ["Partly evidenced", "badge-warn"],
  not_evidenced: ["Not evidenced", "badge-bad"],
  not_applicable: ["Not applicable", ""],
};
const DIMENSION_BADGE = { Strong: "badge-good", Adequate: "badge-info", Weak: "badge-warn", "Critical Defect": "badge-bad" };
const SECTION_BADGE = { Strong: "badge-good", Mixed: "badge-warn", Weak: "badge-bad", "Missing / Critical": "badge-bad" };
const ATS_BADGE = { high: "badge-bad", medium: "badge-warn", low: "badge-info", info: "" };

function fmt(value) {
  return Number(value).toFixed(1).replace(/\.0$/, "");
}

function categoryBlock(cat) {
  const pct = cat.max_points ? (cat.achieved_points / cat.max_points) * 100 : 0;
  const rows = cat.deductions_and_credits
    .map((item) => `<div class="ded">
        <span class="pts ${item.points_impact < 0 ? "neg" : "pos"}">${item.points_impact > 0 ? "+" : ""}${item.points_impact}</span>
        <span>${esc(item.reason)}${item.evidence_ref ? `<span class="faint"> · ${esc(item.evidence_ref)}</span>` : ""}</span>
        ${item.source === "deterministic_rule" ? badge("Rule") : badge("AI", "badge-accent")}
      </div>`)
    .join("");
  return `<details class="acc">
    <summary>
      <div style="flex:1">
        <div class="spread"><b>${esc(cat.category_name)}</b><span><b>${fmt(cat.achieved_points)}</b><span class="faint"> / ${fmt(cat.max_points)} pts</span></span></div>
        ${bar(pct)}
      </div>
    </summary>
    <div class="acc-body stack">
      <div class="row small">
        ${badge(`Rating ${cat.raw_rating_out_of_100}/100`)}${badge(`Rules ${cat.deterministic_subscore}`)}
        ${cat.semantic_subscore != null ? badge(`AI ${cat.semantic_subscore}`, "badge-accent") : badge("No AI subscore")}
        ${badge(`Weight ${cat.weight}`)}
      </div>
      <p class="small muted">${esc(cat.scoring_criteria)}</p>
      ${rows ? `<div><span class="eyebrow">Points gained and lost</span>${rows}</div>` : ""}
      ${cat.supporting_evidence.length ? `<div><span class="eyebrow">Evidence</span>${list(cat.supporting_evidence, "bullets small")}</div>` : ""}
      ${cat.main_weaknesses.length ? `<div><span class="eyebrow">Weaknesses</span>${list(cat.main_weaknesses, "bullets small")}</div>` : ""}
      ${cat.improvement_actions.length ? `<div><span class="eyebrow">How to improve</span>${list(cat.improvement_actions, "bullets small")}</div>` : ""}
      ${cat.uncertainty_note ? `<div class="callout callout-info small">${esc(cat.uncertainty_note)}</div>` : ""}
    </div>
  </details>`;
}

function skillsBlock(skills) {
  const evidenced = skills.evidenced_skills.map((item) => `<span class="badge badge-good" title="${esc(item.evidence)}">${esc(item.skill)}</span>`).join(" ");
  const unsupported = skills.unsupported_skills.map((skill) => badge(skill, "badge-bad")).join(" ");
  const omitted = skills.omitted_demonstrated_skills.map((skill) => badge(skill, "badge-info")).join(" ");
  return `<div class="card stack">
    <h3>Skills credibility</h3>
    <div><span class="eyebrow">Shown in your experience or projects</span><div class="chips">${evidenced || '<span class="faint">None detected</span>'}</div></div>
    <div><span class="eyebrow">Listed but never shown</span><div class="chips">${unsupported || '<span class="faint">None</span>'}</div></div>
    ${omitted ? `<div><span class="eyebrow">Shown but missing from your skills list</span><div class="chips">${omitted}</div></div>` : ""}
    ${skills.recruiter_commentary ? `<p class="small muted">${esc(skills.recruiter_commentary)}</p>` : ""}
  </div>`;
}

function jdBlock(jd) {
  if (!jd.provided) {
    return `<div class="card tint"><h3>Job description match</h3><p class="small muted">No job description was supplied. Paste one on a new review to see each requirement mapped to your CV. Something not evidenced in the CV is not proof that you lack it.</p></div>`;
  }
  const rows = jd.requirements
    .map((req) => {
      const [label, cls] = JD_STATUS[req.status] || [req.status, ""];
      return `<tr><td>${badge(req.importance, req.importance === "Essential" ? "badge-accent" : "")}</td><td>${esc(req.requirement_text)}</td>
        <td>${badge(label, cls)}</td><td class="small">${esc(req.cv_evidence)}<div class="faint">${esc(req.targeted_advice)}</div></td></tr>`;
    })
    .join("");
  return `<div class="card stack">
    <div class="spread"><h3>Job description match</h3>${badge(`${jd.alignment_percentage}% evidenced`, `badge-${scoreTone(jd.alignment_percentage)}`)}</div>
    <p class="small muted">${esc(jd.application_verdict)}</p>
    <table class="table"><thead><tr><th>Importance</th><th>Requirement</th><th>Status</th><th>Evidence in your CV</th></tr></thead><tbody>${rows}</tbody></table>
  </div>`;
}

function atsBlock(diagnostics) {
  const verified = diagnostics.ats_issues.filter((issue) => issue.issue_type === "verified_document_issue");
  const general = diagnostics.ats_issues.filter((issue) => issue.issue_type !== "verified_document_issue");
  const item = (issue) => `<li><div class="row">${badge(issue.severity, ATS_BADGE[issue.severity])}<b>${esc(issue.title)}</b></div>
      <p class="small">${esc(issue.description)}</p><p class="faint">${esc(issue.evidence)}</p><p class="small"><b>Fix:</b> ${esc(issue.remediation)}</p></li>`;
  return `<div class="card stack">
    <h3>Document and ATS checks</h3>
    <p class="faint">${diagnostics.file_format.toUpperCase()} · ${plural(diagnostics.page_count, "page")} · ${diagnostics.word_count} words · ${diagnostics.section_count} sections</p>
    <div><span class="eyebrow">Verified in your document</span><ul class="clean-list">${verified.map(item).join("") || "<li class='small'>No document-level issues were detected.</li>"}</ul></div>
    ${general.length ? `<div><span class="eyebrow">General best practice (not a detected fault)</span><ul class="clean-list">${general.map(item).join("")}</ul></div>` : ""}
  </div>`;
}

function renderScores() {
  const report = currentReport();
  const dimensions = report.dimensions
    .map((dim) => `<details class="acc"><summary><span><b>${esc(dim.dimension_code)}.</b> ${esc(dim.dimension_title)}</span>${badge(dim.verdict_badge, DIMENSION_BADGE[dim.verdict_badge])}</summary>
        <div class="acc-body stack small">
          <p>${esc(dim.recruiter_assessment)}</p>
          ${dim.evidence_quotes.length ? dim.evidence_quotes.map((quote) => `<div class="quote">${esc(quote)}</div>`).join("") : ""}
          ${list(dim.specific_defects, "bullets")}
          <p class="muted"><b>What a recruiter infers:</b> ${esc(dim.recruiter_inference)}</p>
        </div></details>`)
    .join("");
  return `<div class="stack-lg">
    <div class="card">
      <div class="card-title"><h3>Rubric breakdown</h3><span><b>${fmt(report.verdict.overall_score)}</b><span class="faint"> / 100</span></span></div>
      <p class="small muted">Points are calculated by the app from category ratings and your weights. Open a category to see every point gained or lost and where it came from.</p>
      ${report.category_scores.map(categoryBlock).join("")}
    </div>
    <div class="grid-2">${skillsBlock(report.skills_audit)}${atsBlock(state.session.extracted_cv.diagnostics)}</div>
    ${jdBlock(report.jd_comparison)}
    <div class="card"><div class="card-title"><h3>Recruiter dimensions A to J</h3></div>${dimensions}</div>
  </div>`;
}

function renderSections() {
  const report = currentReport();
  const audit = report.deterministic_audit;
  const counts = audit.tier_counts || {};
  const totalTiers = Object.values(counts).reduce((sum, value) => sum + value, 0) || 1;
  const distribution = Object.keys(TIER_LABELS)
    .map((tier) => `<div class="metric"><span>${badge(TIER_LABELS[tier], TIER_BADGE[tier])}</span>${bar(((counts[tier] || 0) / totalTiers) * 100, TIER_BADGE[tier].replace("badge-", ""))}<b>${counts[tier] || 0}</b></div>`)
    .join("");
  const sections = report.section_reviews
    .map((review) => `<div class="card stack">
        <div class="spread"><h3>${esc(review.section_title)}</h3><div class="row">${badge(review.rating, SECTION_BADGE[review.rating])}<b>${review.score_out_of_10}/10</b></div></div>
        <p class="small">${esc(review.summary_verdict)}</p>
        ${review.strengths.length ? `<div><span class="eyebrow">Working</span>${list(review.strengths, "bullets small")}</div>` : ""}
        ${review.weaknesses.length ? `<div><span class="eyebrow">Not working</span>${list(review.weaknesses, "bullets small")}</div>` : ""}
        ${review.key_recommendations.length ? `<div><span class="eyebrow">Do this</span>${list(review.key_recommendations, "bullets small")}</div>` : ""}
      </div>`)
    .join("");
  const bullets = audit.bullet_audits
    .filter((item) => item.word_count >= 4)
    .map((item) => `<li><div class="spread"><span class="small faint">${esc(item.section_name)}</span>${badge(TIER_LABELS[item.evidence_tier], TIER_BADGE[item.evidence_tier])}</div>
        <div>${esc(item.text)}</div><div class="faint">${esc(item.evidence_tier_reason)}</div></li>`)
    .join("");
  return `<div class="stack-lg">
    <div class="grid-2">
      <div class="card stack"><h3>How strong is each line?</h3>
        <p class="small muted">Every line is graded from a generic statement up to a proven result. Recruiters remember the last two levels.</p>${distribution}</div>
      <div class="card stack"><h3>Repetition and filler</h3>
        ${
          audit.duplicate_bullet_pairs.length || Object.keys(audit.repeated_opening_verbs).length || audit.buzzwords_detected.length
            ? `<p class="small">${plural(audit.duplicate_bullet_pairs.length, "duplicate or near-duplicate bullet pair")}, ${plural(Object.keys(audit.repeated_opening_verbs).length, "repeated opening")}, ${plural(audit.buzzwords_detected.length, "buzzword")}.</p>`
            : `<div class="callout callout-good small">No duplicated bullets, repeated openings or buzzwords found.</div>`
        }
        ${audit.buzzwords_detected.length ? `<div class="chips">${audit.buzzwords_detected.map((word) => badge(word, "badge-warn")).join(" ")}</div>` : ""}
        ${audit.unanchored_claims_detected.length ? `<div class="callout callout-warn small">${audit.unanchored_claims_detected.length === 1 ? "1 claim needs" : `${audit.unanchored_claims_detected.length} claims need`} a baseline or method before a recruiter will believe them.</div>` : ""}
      </div>
    </div>
    <div class="grid-auto">${sections}</div>
    <div class="card"><div class="card-title"><h3>Line-by-line evidence</h3></div><ul class="clean-list">${bullets}</ul></div>
  </div>`;
}
