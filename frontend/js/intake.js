/* Intake: file choice, optional targeting, rubric settings, and running an analysis. */
const SAMPLE_LABELS = {
  it_support_weak: "IT support technician (weak)",
  robotics_engineer: "Robotics engineer",
  security_analyst: "Security analyst (SOC)",
  strong_engineer: "Backend engineer (strong)",
  student_projects: "Computer science student",
  unsupported_claims: "Inflated claims",
};
const WEIGHT_LABELS = {
  relevance_alignment: "Role relevance",
  impact_achievements: "Impact",
  experience_project_quality: "Experience and projects",
  skills_credibility: "Skills credibility",
  writing_clarity: "Writing",
  structure_readability: "Structure",
  ats_compatibility: "ATS",
};
const PRESET_LABELS = {
  default: "Balanced (default)",
  student_graduate: "Student / graduate",
  technical_engineering: "Technical / engineering",
  senior_leadership: "Senior / leadership",
};
const STEPS = ["Reading the document", "Checking evidence", "Matching likely roles", "Scoring the rubric", "Building your plan"];

async function loadConfig() {
  state.config = await api("/api/config");
  const cfg = state.config;
  $("#max-mb").textContent = cfg.max_upload_mb;
  $("#privacy-text").textContent = cfg.privacy;
  $("#model").innerHTML = cfg.supported_models
    .map((model) => `<option ${model === cfg.model ? "selected" : ""}>${esc(model)}</option>`)
    .join("");
  $("#preset").innerHTML = Object.keys(cfg.presets)
    .map((key) => `<option value="${esc(key)}">${esc(PRESET_LABELS[key] || key)}</option>`)
    .join("");
  renderWeights(cfg.presets.default);
  updateEngineStatus();
}

function updateEngineStatus() {
  const { has_api_key: hasKey, model } = state.config;
  const toggle = $("#use-llm");
  toggle.disabled = !hasKey;
  if (!hasKey) toggle.checked = false;
  $("#llm-note").textContent = hasKey ? `(${model}; sends the extracted CV text to Google)` : "(add a Gemini key below to enable)";
  const pill = $("#engine-pill");
  const usingModel = hasKey && toggle.checked;
  pill.className = `badge ${usingModel ? "badge-accent" : ""}`;
  pill.textContent = usingModel ? `Rules + ${model}` : "Local rules only";
}

function renderWeights(weights) {
  $("#weights-grid").innerHTML = Object.entries(WEIGHT_LABELS)
    .map(([key, label]) => `<label>${esc(label)}<input type="number" min="0" max="100" step="1" data-weight="${key}" value="${Number(weights[key] ?? 0)}"></label>`)
    .join("");
  updateWeightTotal();
}

function readWeights() {
  const weights = {};
  $$("[data-weight]").forEach((input) => {
    weights[input.dataset.weight] = Math.max(0, Math.min(100, parseInt(input.value, 10) || 0));
  });
  return weights;
}

function updateWeightTotal() {
  const total = Object.values(readWeights()).reduce((sum, value) => sum + value, 0);
  const node = $("#weights-total");
  node.textContent = total === 100 ? "Total 100" : `Total ${total} (scaled to 100)`;
  node.classList.toggle("off", total === 0);
}

async function loadSamples() {
  const { samples } = await api("/api/samples");
  $("#sample-chips").innerHTML = samples
    .map((name) => `<button type="button" class="chip" data-sample="${esc(name)}">${esc(SAMPLE_LABELS[name] || name.replace(/_/g, " "))}</button>`)
    .join("");
}

function chooseFile(file) {
  if (!file) return;
  const extension = file.name.toLowerCase().split(".").pop();
  if (!["pdf", "docx"].includes(extension)) {
    toast("Upload a PDF or DOCX file.", "error");
    return;
  }
  const limitMb = state.config ? state.config.max_upload_mb : 10;
  if (file.size > limitMb * 1024 * 1024) {
    toast(`That file is over the ${limitMb} MB limit.`, "error");
    return;
  }
  state.file = file;
  const chip = $("#file-chip");
  chip.innerHTML = `&#128206; ${esc(file.name)} <span class="faint">${Math.max(1, Math.round(file.size / 1024))} KB</span>
    <button type="button" class="btn btn-ghost btn-sm" data-clear-file>Remove</button>`;
  chip.classList.remove("hidden");
  $("#analyse-btn").disabled = false;
}

function clearFile() {
  state.file = null;
  $("#file-input").value = "";
  $("#file-chip").classList.add("hidden");
  $("#analyse-btn").disabled = true;
}

function contextForm() {
  const form = new FormData();
  form.append("target_job_title", $("#target-title").value.trim());
  form.append("target_industry", $("#target-industry").value.trim());
  form.append("career_level", $("#career-level").value);
  form.append("job_description", $("#job-description").value.trim());
  form.append("language", "en-GB");
  form.append("use_llm", $("#use-llm").checked ? "true" : "false");
  form.append("weights_json", JSON.stringify(readWeights()));
  return form;
}

function startStepper() {
  const node = $("#stepper");
  let index = 0;
  const paint = () => {
    node.innerHTML = STEPS.map(
      (label, i) => `<div class="step ${i < index ? "done" : i === index ? "active" : ""}"><span class="dot"></span>${esc(label)}</div>`
    ).join("");
  };
  node.classList.remove("hidden");
  paint();
  const timer = setInterval(() => {
    if (index < STEPS.length - 1) {
      index += 1;
      paint();
    }
  }, 650);
  return () => {
    clearInterval(timer);
    index = STEPS.length;
    paint();
    setTimeout(() => node.classList.add("hidden"), 350);
  };
}

async function runAnalysis(sampleName) {
  if (state.busy) return;
  if (!sampleName && !state.file) {
    toast("Choose a CV file or a sample first.");
    return;
  }
  state.busy = true;
  $("#analyse-btn").disabled = true;
  const stop = startStepper();
  try {
    const form = contextForm();
    let session;
    if (sampleName) {
      session = await api(`/api/samples/${encodeURIComponent(sampleName)}/analyze`, { method: "POST", body: form });
    } else {
      form.append("file", state.file);
      session = await api("/api/analyze", { method: "POST", body: form });
    }
    stop();
    openSession(session, "overview");
  } catch (error) {
    stop();
    toast(error.message, "error");
  } finally {
    state.busy = false;
    $("#analyse-btn").disabled = !state.file;
  }
}

async function saveSettings() {
  try {
    const result = await postJSON("/api/config", { gemini_api_key: $("#api-key").value.trim(), gemini_model: $("#model").value });
    $("#api-key").value = "";
    state.config.has_api_key = result.has_api_key;
    state.config.model = result.model;
    updateEngineStatus();
    toast(result.has_api_key ? "AI settings saved for this server session." : "No key set, so the local rules will be used.");
  } catch (error) {
    toast(error.message, "error");
  }
}

function bindIntake() {
  const zone = $("#dropzone");
  const input = $("#file-input");
  zone.addEventListener("click", () => input.click());
  zone.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      input.click();
    }
  });
  input.addEventListener("change", () => chooseFile(input.files[0]));
  ["dragenter", "dragover"].forEach((type) =>
    zone.addEventListener(type, (event) => {
      event.preventDefault();
      zone.classList.add("drag");
    })
  );
  ["dragleave", "drop"].forEach((type) =>
    zone.addEventListener(type, (event) => {
      event.preventDefault();
      zone.classList.remove("drag");
    })
  );
  zone.addEventListener("drop", (event) => chooseFile(event.dataTransfer.files[0]));
  $("#file-chip").addEventListener("click", (event) => {
    if (event.target.closest("[data-clear-file]")) clearFile();
  });
  $("#sample-chips").addEventListener("click", (event) => {
    const chip = event.target.closest("[data-sample]");
    if (chip) runAnalysis(chip.dataset.sample);
  });
  $("#intake-form").addEventListener("submit", (event) => {
    event.preventDefault();
    runAnalysis();
  });
  $("#preset").addEventListener("change", (event) => renderWeights(state.config.presets[event.target.value]));
  $("#weights-grid").addEventListener("input", updateWeightTotal);
  $("#use-llm").addEventListener("change", updateEngineStatus);
  $("#save-settings").addEventListener("click", saveSettings);
}
