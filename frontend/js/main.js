/* Tabs, results header, event wiring, and start-up. */
const TABS = [
  ["overview", "Overview", renderOverview],
  ["roles", "Role targets", renderRoles],
  ["plan", "Elevation plan", renderPlan],
  ["scores", "Score breakdown", renderScores],
  ["sections", "Sections", renderSections],
  ["edits", "Edits", renderEdits],
  ["document", "Revised CV", renderDocument],
  ["reassess", "Reassess", renderReassess],
];

function renderHeader() {
  const session = state.session;
  const report = session.initial_report;
  const ctx = session.context;
  const primary = primaryTarget(report);
  const level = `${LEVEL_LABELS[ctx.career_level] || ctx.career_level}${ctx.career_level_source === "inferred" ? " (inferred)" : ""}`;
  const target = primary ? `${primary.title}${primary.is_user_target ? "" : " (inferred)"}` : ctx.target_job_title || "None";
  $("#result-head").innerHTML = `<div>
      <span class="eyebrow">Review of ${esc(session.extracted_cv.diagnostics.filename)}</span>
      <h1>${esc(session.extracted_cv.contact.name || "Your CV")}</h1>
      <div class="meta">
        ${badge(`Score ${Math.round(report.verdict.overall_score)}/100`, `badge-${scoreTone(report.verdict.overall_score)}`)}
        ${badge(`Level: ${level}`)}
        ${badge(`Target: ${target}`, "badge-accent")}
        ${ctx.job_description ? badge("Job description supplied", "badge-info") : ""}
      </div>
    </div>
    <div class="row no-print"><button class="btn" data-goto="roles">Change target</button><button class="btn" data-new-review>New review</button></div>`;
}

function renderTabs() {
  const pending = pendingCount();
  $("#tabs").innerHTML = TABS.map(([key, label]) => {
    const extra = key === "edits" && pending ? `<span class="count">${pending}</span>` : key === "reassess" && state.session.latest_reassessment ? '<span class="count">&#10003;</span>' : "";
    return `<button class="tab ${state.tab === key ? "active" : ""}" role="tab" aria-selected="${state.tab === key}" data-tab="${key}">${esc(label)}${extra}</button>`;
  }).join("");
}

function refreshView() {
  if (!state.session) return;
  renderHeader();
  renderTabs();
  const tab = TABS.find(([key]) => key === state.tab) || TABS[0];
  try {
    $("#panel").innerHTML = tab[2]();
  } catch (error) {
    console.error(error);
    $("#panel").innerHTML = emptyState(`This view could not be displayed (${error.message}).`);
  }
}

function openSession(session, tab = "overview") {
  state.session = session;
  state.tab = tab;
  state.editFilter = "pending";
  state.editingRec = null;
  $("#intake-view").classList.add("hidden");
  $("#results-view").classList.remove("hidden");
  $("#new-review-btn").classList.remove("hidden");
  refreshView();
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function newReview() {
  state.session = null;
  $("#results-view").classList.add("hidden");
  $("#intake-view").classList.remove("hidden");
  $("#new-review-btn").classList.add("hidden");
  window.scrollTo({ top: 0 });
}

function hasDecisions() {
  const report = currentReport();
  return report.recommendations.some((rec) => rec.status !== "pending") || report.follow_up_questions.some((q) => q.resolution_type !== "unanswered");
}

async function retarget(payload) {
  if (hasDecisions() && !window.confirm("Re-run the review for this role? Decisions made in this session will be discarded.")) return;
  try {
    toast("Re-running the review for the new target...");
    const session = await postJSON(`/api/sessions/${state.session.session_id}/retarget`, payload);
    openSession(session, "roles");
    toast(`Now targeting ${session.initial_report.role_targets.primary_title || session.context.target_job_title}.`);
  } catch (error) {
    toast(error.message, "error");
  }
}

function handlePanelClick(event) {
  const goto = event.target.closest("[data-goto]");
  if (goto) {
    state.tab = goto.dataset.goto;
    refreshView();
    window.scrollTo({ top: 0, behavior: "smooth" });
    return;
  }
  if (event.target.closest("[data-new-review]")) {
    newReview();
    return;
  }
  const role = event.target.closest("[data-retarget]");
  if (role) {
    retarget({ role_id: role.dataset.retarget });
    return;
  }
  if (event.target.closest("[data-retarget-custom]")) {
    const title = $("#retarget-title").value.trim();
    retarget(title ? { target_job_title: title } : { role_id: $("#retarget-select").value });
    return;
  }
  if (handleEditsClick(event)) return;
  handleDocumentClick(event);
}

async function init() {
  bindIntake();
  $("#tabs").addEventListener("click", (event) => {
    const tab = event.target.closest("[data-tab]");
    if (!tab) return;
    state.tab = tab.dataset.tab;
    state.editingRec = null;
    refreshView();
  });
  $("#panel").addEventListener("click", handlePanelClick);
  $("#result-head").addEventListener("click", handlePanelClick);
  $("#panel").addEventListener("change", handleDocumentChange);
  $("#new-review-btn").addEventListener("click", newReview);
  $("#privacy-btn").addEventListener("click", () => $("#privacy-dialog").showModal());
  $("#privacy-close").addEventListener("click", () => $("#privacy-dialog").close());
  try {
    await loadConfig();
    await loadSamples();
  } catch (error) {
    toast(`Could not reach the local server: ${error.message}`, "error");
  }
}

document.addEventListener("DOMContentLoaded", init);
