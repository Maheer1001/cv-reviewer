/* Revised CV preview, export, and reassessment tabs. */
const HEADER_TYPES = new Set(["experience", "projects", "education"]);

function previewSection(section) {
  const parts = [];
  let bullets = [];
  const flush = () => {
    if (bullets.length) parts.push(`<ul>${bullets.join("")}</ul>`);
    bullets = [];
  };
  section.entries.forEach((entry) => {
    const cls = entry.is_deleted ? "removed" : entry.is_added ? "added" : entry.current_text !== entry.original_text ? "changed" : "";
    const text = markPlaceholders(entry.current_text);
    if (entry.is_bullet) {
      bullets.push(`<li class="entry ${cls}">${text}</li>`);
    } else {
      flush();
      parts.push(`<p class="entry ${cls}">${HEADER_TYPES.has(section.normalized_type) ? `<b>${text}</b>` : text}</p>`);
    }
  });
  flush();
  return `<h2>${esc(section.title)}</h2>${parts.join("")}`;
}

function renderDocument() {
  const working = state.session.working_cv;
  const contact = working.contact;
  const contactLine = [contact.email, contact.phone, contact.location, contact.linkedin, contact.github, ...(contact.portfolio_links || [])]
    .filter(Boolean)
    .filter((value, index, all) => all.indexOf(value) === index)
    .map(esc)
    .join(" · ");
  const sections = working.sections.filter((section) => section.normalized_type !== "contact").map(previewSection).join("");
  const flags = working.unresolved_placeholders || [];
  const history = [...working.change_history]
    .reverse()
    .slice(0, 30)
    .map((event) => `<li class="small"><div class="row">${badge(event.action_taken)}<span class="faint">${esc(event.section_name)}</span></div>
        ${beforeAfter(event.before_text, event.after_text, ["Before", "After"])}</li>`)
    .join("");
  return `<div class="stack-lg">
    <div class="card stack no-print">
      <div class="spread">
        <div><h3>Revised CV</h3><p class="small muted">Built only from the edits you accepted. ${working.accepted_count} accepted, ${working.pending_count} still pending.</p></div>
        <label class="toggle small"><input type="checkbox" id="show-changes" ${state.showChanges === false ? "" : "checked"}> Highlight changes</label>
      </div>
      ${flags.length
        ? `<div class="callout callout-warn small"><b>${flags.length === 1 ? "1 placeholder still needs a real detail:" : `${flags.length} placeholders still need real details:`}</b>${list(flags.slice(0, 8), "bullets")}
            <label class="toggle" style="margin-top:6px"><input type="checkbox" id="ack-placeholders"> I understand these will appear in the export as written</label></div>`
        : `<div class="callout callout-good small">No unresolved placeholders. The revised CV is ready to export.</div>`}
      <div class="row">
        <button class="btn btn-primary" data-export="docx">Download DOCX</button>
        <button class="btn" data-export="pdf">Download PDF</button>
        <button class="btn" data-export="summary">Change summary</button>
        <button class="btn btn-ghost" data-goto="reassess">Reassess this version</button>
      </div>
    </div>
    <div class="paper ${state.showChanges === false ? "clean" : ""}">
      <h1>${esc(contact.name || "Your name")}</h1>
      <div class="contact">${contactLine}</div>
      ${sections}
    </div>
    ${history ? `<details class="card flat no-print"><summary style="cursor:pointer"><b>Change history (${working.change_history.length})</b></summary><ul class="clean-list" style="margin-top:8px">${history}</ul></details>` : ""}
  </div>`;
}

function renderReassess() {
  const comparison = state.session.latest_reassessment;
  const intro = `<div class="card stack">
      <h3>Reassess the revised CV</h3>
      <p class="small muted">The revised CV is re-read and scored with the same rubric, weights and role target. Rewording alone will not move the score; new evidence will.</p>
      <div class="row"><button class="btn btn-primary" data-reassess>${comparison ? "Reassess again" : "Reassess revised CV"}</button></div>
    </div>`;
  if (!comparison) return `<div class="stack-lg">${intro}</div>`;
  const delta = comparison.score_delta;
  const deltaBadge = badge(`${delta > 0 ? "+" : ""}${fmt(delta)} points`, delta > 0 ? "badge-good" : delta < 0 ? "badge-bad" : "");
  const rows = comparison.category_deltas
    .map((item) => `<tr><td>${esc(item.category_name)}</td><td>${fmt(item.original_points)}</td><td>${fmt(item.revised_points)}</td>
        <td><b style="color:${item.delta_points > 0 ? "var(--good)" : item.delta_points < 0 ? "var(--bad)" : "inherit"}">${item.delta_points > 0 ? "+" : ""}${fmt(item.delta_points)}</b></td>
        <td class="small muted">${esc(item.evidence_of_change)}</td></tr>`)
    .join("");
  const block = (title, items, cls) => (items.length ? `<div class="card stack"><h3>${esc(title)}</h3>${list(items, `bullets small ${cls || ""}`)}</div>` : "");
  return `<div class="stack-lg">
    <div class="card">
      <div class="score-hero">
        ${ring(comparison.revised_score, "revised score")}
        <div class="stack">
          <div class="row">${badge(`Was ${fmt(comparison.original_score)}`)}${deltaBadge}</div>
          <h2>${esc(comparison.reassessment_verdict)}</h2>
        </div>
      </div>
    </div>
    <div class="card"><div class="card-title"><h3>What changed and why</h3></div>
      <table class="table"><thead><tr><th>Category</th><th>Before</th><th>After</th><th>Change</th><th>Reason</th></tr></thead><tbody>${rows}</tbody></table></div>
    <div class="grid-2">
      ${block("Improvements verified", comparison.improvements_verified)}
      ${block("New problems introduced", comparison.new_problems_introduced)}
      ${block("Still weak", comparison.remaining_weaknesses)}
      ${block("Rejected edits worth another look", comparison.rejected_worth_reconsidering)}
      ${block("Unresolved questions or missing details", comparison.unresolved_questions_or_missing_info)}
    </div>
    ${intro}
  </div>`;
}

async function exportCv(format) {
  const acknowledged = $("#ack-placeholders") ? $("#ack-placeholders").checked : false;
  const url = `/api/sessions/${state.session.session_id}/export?export_format=${format}&acknowledge_placeholders=${acknowledged}`;
  try {
    const response = await fetch(url);
    if (response.status === 409) {
      const body = await response.json();
      toast(`${body.detail} Tick the confirmation box to export anyway.`, "error");
      return;
    }
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(body.detail || `Export failed (${response.status}).`);
    }
    const blob = await response.blob();
    const match = (response.headers.get("content-disposition") || "").match(/filename="([^"]+)"/);
    const name = match ? match[1] : `revised-cv.${format === "summary" ? "txt" : format}`;
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = name;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(link.href), 1500);
    toast(`Downloaded ${name}`);
  } catch (error) {
    toast(error.message, "error");
  }
}

async function runReassess(button) {
  button.disabled = true;
  button.textContent = "Reassessing...";
  try {
    state.session = await postJSON(`/api/sessions/${state.session.session_id}/reassess`);
    state.tab = "reassess";
    refreshView();
    toast("Reassessed with the same rubric and role target.");
  } catch (error) {
    toast(error.message, "error");
    button.disabled = false;
    button.textContent = "Reassess revised CV";
  }
}

function handleDocumentClick(event) {
  const exportButton = event.target.closest("[data-export]");
  if (exportButton) {
    exportCv(exportButton.dataset.export);
    return true;
  }
  const reassessButton = event.target.closest("[data-reassess]");
  if (reassessButton) {
    runReassess(reassessButton);
    return true;
  }
  return false;
}

function handleDocumentChange(event) {
  if (event.target.id === "show-changes") {
    state.showChanges = event.target.checked;
    $(".paper").classList.toggle("clean", !state.showChanges);
    return true;
  }
  return false;
}
