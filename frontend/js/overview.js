/* Overview, role targets, and elevation plan tabs. */
const RATING_BADGE = {
  "Highly Competitive": "badge-good",
  "Moderately Competitive": "badge-info",
  "Borderline / At Risk of Rejection": "badge-warn",
  "Uncompetitive in Current Form": "badge-bad",
  "Insufficient Role Context": "",
};
const KIND_LABELS = {
  add_now_if_true: "Add if true",
  start_doing: "Start doing",
  build_evidence: "Build evidence",
  credential: "Optional credential",
};

function primaryTarget(report) {
  const targets = report.role_targets;
  return targets ? targets.candidates.find((candidate) => candidate.is_primary) : null;
}

function renderOverview() {
  const report = currentReport();
  const verdict = report.verdict;
  const pillars = report.three_pillars;
  const primary = primaryTarget(report);
  const plan = report.elevation_plan;
  const suitability = pillars.role_suitability_assessed
    ? `<b>${pillars.role_suitability_score}%</b> of the job description's weighted requirements are evidenced.`
    : `Not assessed without a job description.${primary ? ` Indicative fit for <b>${esc(primary.title)}</b>: <b>${primary.fit_percentage}%</b> coverage of typical requirements.` : ""}`;
  const weaknesses = report.top_weaknesses
    .map((item) => `<li class="weakness"><span class="num">${item.rank}</span><div>
        <b>${esc(item.problem_title)}</b>
        ${item.exact_problem !== item.problem_title ? `<p class="small">${esc(item.exact_problem)}</p>` : ""}
        <p class="faint">Where: ${esc(item.where_it_appears)}</p>
        <p class="small"><b>Fix:</b> ${esc(item.how_to_address)}</p>
      </div></li>`)
    .join("");
  const steps = report.prioritised_action_plan
    .slice(0, 3)
    .map((step) => `<li><div class="row">${badge(step.priority, PRIORITY_BADGE[step.priority])}<b>${esc(step.action_title)}</b></div>
        <p class="small muted">${esc(step.rationale)}</p></li>`)
    .join("");
  return `<div class="stack-lg">
    <div class="card">
      <div class="score-hero">
        ${ring(verdict.overall_score)}
        <div class="stack">
          <div class="row">${badge(scoreBand(verdict.overall_score), `badge-${scoreTone(verdict.overall_score)}`)}${badge(pillars.application_competitiveness_rating, RATING_BADGE[pillars.application_competitiveness_rating])}</div>
          <h2>${esc(verdict.blunt_recruiter_verdict)}</h2>
          <div class="grid-2">
            <div><span class="eyebrow">Strongest evidence</span><p>${esc(verdict.strongest_aspect)}</p></div>
            <div><span class="eyebrow">Biggest problem</span><p>${esc(verdict.biggest_weakness)}</p></div>
          </div>
        </div>
      </div>
    </div>

    <div class="grid-3">
      <div class="card"><span class="eyebrow">1 · General CV quality</span>
        <h2>${pillars.general_cv_quality_score}<span class="faint"> / 100</span></h2>
        <p class="small muted">${esc(pillars.general_cv_quality_verdict)}</p></div>
      <div class="card"><span class="eyebrow">2 · Role suitability</span>
        <p>${suitability}</p>
        <button class="btn btn-sm" data-goto="roles">See role targets</button></div>
      <div class="card"><span class="eyebrow">3 · Competitiveness</span>
        <p>${badge(pillars.application_competitiveness_rating, RATING_BADGE[pillars.application_competitiveness_rating])}</p>
        <p class="small muted">${esc(pillars.application_competitiveness_verdict)}</p></div>
    </div>

    <div class="grid-2">
      <div class="card"><div class="card-title"><h3>Top weaknesses</h3><span class="faint">ranked by points lost</span></div>
        <ul class="clean-list">${weaknesses || "<li>No major weaknesses were detected.</li>"}</ul></div>
      <div class="card stack">
        <div class="card-title"><h3>What to do next</h3></div>
        ${plan ? `<div class="callout callout-info">${esc(plan.headline)}</div>` : ""}
        <ul class="clean-list">${steps}</ul>
        <div class="row">
          <button class="btn btn-primary" data-goto="plan">Open the elevation plan</button>
          <button class="btn" data-goto="edits">Start editing (${pendingCount()} pending)</button>
        </div>
      </div>
    </div>

    <details class="card flat">
      <summary class="spread" style="cursor:pointer"><b>How this was assessed, and what it cannot tell you</b><span class="faint">${esc(verdict.analysis_engine_used)}</span></summary>
      <div class="stack" style="margin-top:12px">
        <p class="small">${esc(verdict.career_stage_calibration_note)}</p>
        ${list(verdict.important_limitations_and_uncertainties, "bullets small muted")}
      </div>
    </details>
  </div>`;
}

function competencyStatus(comp) {
  if (comp.coverage === "missing") return ["missing", "&#10005;", "Missing"];
  if (comp.coverage === "skills_list_only") return ["listed", "&#9675;", "Skills list only"];
  if (comp.coverage === "summary_only") return ["listed", "&#9675;", "Mentioned, not shown"];
  if (comp.depth === "mentioned") return ["partial", "&#9680;", "Shown as a duty"];
  return ["proven", "&#10003;", comp.depth === "proven" ? "Proven with evidence" : "Described with detail"];
}

function roleCard(target) {
  const competencies = target.competencies
    .map((comp) => {
      const [cls, icon, label] = competencyStatus(comp);
      return `<div class="comp"><span class="ic ${cls}">${icon}</span><div>
          <b>${esc(comp.label)}</b>${comp.essential ? ' <span class="faint">essential</span>' : ""} · <span class="small">${label}</span>
          ${comp.evidence_quote ? `<span class="q">"${esc(comp.evidence_quote)}"</span>` : ""}
        </div></div>`;
    })
    .join("");
  const ribbon = target.is_user_target ? badge("Your target", "badge-accent") : target.is_primary ? badge("Best match", "badge-accent") : "";
  return `<div class="card role-card ${target.is_primary ? "primary" : ""} stack">
    ${ribbon ? `<span class="ribbon">${ribbon}</span>` : ""}
    <div class="spread">
      <div><h3>${esc(target.title)}</h3><span class="faint">${esc(target.family)}</span></div>
      <div class="row">${badge(target.readiness, READINESS_BADGE[target.readiness])}${badge(`${target.confidence} confidence`)}</div>
    </div>
    <div class="stack">
      <div class="metric"><span>Coverage</span>${bar(target.fit_percentage)}<b>${target.fit_percentage}%</b></div>
      <div class="metric"><span>Evidence depth</span>${bar(target.evidence_strength)}<b>${target.evidence_strength}%</b></div>
    </div>
    <div><span class="eyebrow">Why this role</span>${list(target.why_inferred, "bullets small")}</div>
    <div><span class="eyebrow">What recruiters screen for</span><div class="competencies">${competencies}</div></div>
    ${target.top_gaps.length ? `<div><span class="eyebrow">Gaps to close</span>${list(target.top_gaps, "bullets small")}</div>` : ""}
    <div><span class="eyebrow">Next steps</span>${list(target.next_steps, "bullets small")}</div>
    <div class="callout callout-info small"><b>What a strong CV for this role shows:</b> ${esc(target.benchmark)}</div>
    ${target.is_primary ? "" : `<button class="btn" data-retarget="${esc(target.role_id)}">Re-run the review for this role</button>`}
  </div>`;
}

function renderRoles() {
  const targets = currentReport().role_targets;
  if (!targets) return emptyState("Role targeting is not available for this review.");
  let intro;
  if (!targets.role_was_specified) {
    intro = `You didn't name a target, so the reviewer matched your CV against ${state.config.roles.length} role profiles. These are the roles it most resembles, with what each would need.`;
  } else if (targets.specified_title_matched_profile) {
    intro = `Measured against your target, <b>${esc(targets.specified_title)}</b>, alongside the closest alternatives your evidence supports.`;
  } else {
    intro = `No built-in profile matches <b>${esc(targets.specified_title)}</b>, so these are the closest roles your evidence supports.`;
  }
  const level = `${LEVEL_LABELS[targets.career_level_used] || targets.career_level_used}${targets.career_level_source === "inferred" ? " (inferred)" : ""}`;
  const families = {};
  state.config.roles.forEach((role) => {
    (families[role.family] = families[role.family] || []).push(role);
  });
  const options = Object.entries(families)
    .map(([family, roles]) => `<optgroup label="${esc(family)}">${roles.map((role) => `<option value="${esc(role.role_id)}">${esc(role.title)}</option>`).join("")}</optgroup>`)
    .join("");
  const suggestions = targets.semantic_suggestions.length
    ? `<div class="card tint"><span class="eyebrow">Also suggested by the AI model (checked against your CV text)</span>${list(targets.semantic_suggestions, "bullets small")}</div>`
    : "";
  return `<div class="stack-lg">
    <div class="card stack">
      <p>${intro}</p>
      <div class="row small">${badge(`Career level: ${level}`)}${targets.career_level_reason ? `<span class="faint">${esc(targets.career_level_reason)}</span>` : ""}</div>
      <details><summary class="faint" style="cursor:pointer">How fit is calculated</summary><p class="small muted" style="margin-top:8px">${esc(targets.method_note)}</p></details>
    </div>
    <div class="grid-auto">${targets.candidates.map(roleCard).join("")}</div>
    ${suggestions}
    <div class="card stack">
      <h3>Target a different role</h3>
      <p class="small muted">This starts a fresh review of the same CV against the new role. Decisions made in this session are discarded.</p>
      <div class="grid-2">
        <label class="field">Choose a role profile<select id="retarget-select">${options}</select></label>
        <label class="field">Or type a job title<input type="text" id="retarget-title" maxlength="120" placeholder="e.g. Junior Data Engineer"></label>
      </div>
      <div class="row"><button class="btn btn-primary" data-retarget-custom>Re-run the review</button></div>
    </div>
  </div>`;
}

function actionCard(action) {
  return `<div class="card flat stack">
    <div class="spread"><b>${esc(action.title)}</b><div class="row">${badge(KIND_LABELS[action.kind] || action.kind, action.kind === "credential" ? "" : "badge-accent")}${badge(`${action.effort} effort`)}</div></div>
    <p class="small">${esc(action.detail)}</p>
    <p class="small muted">${esc(action.why)}</p>
    ${action.for_roles.length ? `<div class="row">${action.for_roles.map((role) => badge(role, "badge-info")).join("")}</div>` : ""}
    ${action.cv_line_once_done ? `<div><span class="eyebrow">Once true, your CV could say</span><div class="cv-line">${markPlaceholders(action.cv_line_once_done)}</div></div>` : ""}
    ${action.rubric_effect ? `<p class="faint">Effect: ${esc(action.rubric_effect)}</p>` : ""}
  </div>`;
}

function renderPlan() {
  const plan = currentReport().elevation_plan;
  if (!plan) return emptyState("The elevation plan is not available for this review.");
  const upgrades = plan.writing_upgrades
    .map((item) => `<div class="card stack">
        <div class="spread"><h3>${esc(item.title)}</h3><div class="row">${badge(item.priority, PRIORITY_BADGE[item.priority])}${item.affected_count ? badge(`${item.affected_count} affected`) : ""}</div></div>
        <p>${esc(item.problem)}</p>
        <p class="small muted">${esc(item.why_it_matters)}</p>
        <p class="small"><b>How:</b> ${esc(item.how_to_fix)}</p>
        ${beforeAfter(item.example_before, item.example_after, ["From your CV", "Stronger version"])}
      </div>`)
    .join("");
  const timeframes = ["This week", "Next 30 days", "Next 90 days"]
    .map((frame) => {
      const items = plan.actions_to_begin.filter((action) => action.timeframe === frame);
      if (!items.length) return "";
      return `<div><div class="timeframe"><h3>${esc(frame)}</h3>${badge(`${items.length}`)}</div><div class="grid-auto">${items.map(actionCard).join("")}</div></div>`;
    })
    .join("");
  return `<div class="stack-lg">
    <div class="card plan-banner"><span class="eyebrow">Your elevation plan</span><p>${esc(plan.headline)}</p></div>
    <section class="stack">
      <div class="spread"><h2>1. Improve the writing</h2><span class="faint">Uses your own lines; [brackets] mark facts only you can supply</span></div>
      ${upgrades || emptyState("No significant writing problems were detected.")}
    </section>
    <section class="stack">
      <h2>2. Add now, if true</h2>
      <div class="grid-auto">${plan.add_now_if_true.map(actionCard).join("") || emptyState("Nothing obvious is missing.")}</div>
    </section>
    <section class="stack">
      <h2>3. Things to begin</h2>
      ${timeframes || emptyState("No new activity is needed for your current targets.")}
    </section>
    <div class="callout callout-warn">${esc(plan.honesty_note)}</div>
  </div>`;
}
