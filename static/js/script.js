// ResumeMatch AI -- frontend logic
// Handles file selection, calls the /api/analyze endpoint, and renders
// the ranked, explainable results table + candidate detail modal.
// NOTE: all element IDs and API calls are unchanged from the original
// implementation -- only presentation/UX logic was added on top.

const dropzone = document.getElementById("dropzone");
const fileInput = document.getElementById("resumes");
const fileListEl = document.getElementById("file-list");
const fileListHeader = document.getElementById("file-list-header");
const fileCountLabel = document.getElementById("file-count-label");
const clearFilesBtn = document.getElementById("clear-files-btn");
const analyzeBtn = document.getElementById("analyze-btn");
const analyzeBtnLabel = document.getElementById("analyze-btn-label");
const statusLine = document.getElementById("status-line");

const emptyState = document.getElementById("empty-state");
const metaLine = document.getElementById("meta-line");
const resultsActions = document.getElementById("results-actions");
const resultsTableWrap = document.getElementById("results-table-wrap");
const resultsBody = document.getElementById("results-body");

const searchBox = document.getElementById("search-box");
const sortSelect = document.getElementById("sort-select");
const minScoreSelect = document.getElementById("min-score-select");

const modalOverlay = document.getElementById("detail-modal");
const modalContent = document.getElementById("modal-content");
const modalClose = document.getElementById("modal-close");
const modalBox = modalOverlay.querySelector(".modal");

const compareBar = document.getElementById("compare-bar");
const compareCountLabel = document.getElementById("compare-count-label");
const compareClearBtn = document.getElementById("compare-clear-btn");
const compareBtn = document.getElementById("compare-btn");
let selectedForCompare = new Set();

const jdRecap = document.getElementById("jd-recap");
const jdRecapText = document.getElementById("jd-recap-text");
const jobTitleInput = document.getElementById("job_title");
const jobDescriptionInput = document.getElementById("job_description");
const savedJobsSelect = document.getElementById("saved-jobs-select");
const deleteSavedJobBtn = document.getElementById("delete-saved-job-btn");
const historySelect = document.getElementById("history-select");
const historyRow = document.getElementById("history-row");
const deleteHistoryBtn = document.getElementById("delete-history-btn");

let selectedFiles = [];
let currentResults = [];
let savedJobs = [];
let historyList = [];

// ---------- Icons used inside dynamically generated markup ----------

const ICONS = {
  check: '<svg class="icon icon-sm" viewBox="0 0 24 24"><path d="M20 6 9 17l-5-5"/></svg>',
  alert: '<svg class="icon icon-sm" viewBox="0 0 24 24"><path d="M12 9v4M12 17h.01M10.29 3.86 1.82 18a1.5 1.5 0 0 0 1.29 2.25h17.78A1.5 1.5 0 0 0 22.18 18L13.71 3.86a1.5 1.5 0 0 0-2.62 0z"/></svg>',
  spinner: '<svg class="icon spin" viewBox="0 0 24 24"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>',
  file: '<svg class="icon icon-sm file-icon" viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/></svg>',
  trash: '<svg class="icon icon-sm" viewBox="0 0 24 24"><path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2m3 0-1 14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2L4 6"/></svg>',
  eye: '<svg class="icon icon-sm" viewBox="0 0 24 24"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>',
  info: '<svg class="icon icon-sm" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/></svg>',
  star: '<svg class="icon icon-sm" viewBox="0 0 24 24"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg>',
};

// ---------- Theme (light/dark) ----------

const THEME_KEY = "resumeMatchAI.theme";
const themeToggle = document.getElementById("theme-toggle");

function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  themeToggle.setAttribute("aria-pressed", String(theme === "dark"));
  localStorage.setItem(THEME_KEY, theme);
}

(function initTheme() {
  const saved = localStorage.getItem(THEME_KEY);
  if (saved) {
    applyTheme(saved);
  } else {
    const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    applyTheme(prefersDark ? "dark" : "light");
  }
})();

themeToggle.addEventListener("click", () => {
  const current = document.documentElement.getAttribute("data-theme");
  applyTheme(current === "dark" ? "light" : "dark");
});

// ---------- Persist job description locally so it survives a page reload ----------

const JD_STORAGE_KEY = "resumeMatchAI.jobDescriptionDraft";

function saveJobDraft() {
  localStorage.setItem(
    JD_STORAGE_KEY,
    JSON.stringify({ title: jobTitleInput.value, description: jobDescriptionInput.value })
  );
}

function restoreJobDraft() {
  const saved = localStorage.getItem(JD_STORAGE_KEY);
  if (!saved) return;
  try {
    const { title, description } = JSON.parse(saved);
    if (title) jobTitleInput.value = title;
    if (description) jobDescriptionInput.value = description;
  } catch (e) {
    /* ignore malformed saved draft */
  }
}

restoreJobDraft();
jobTitleInput.addEventListener("input", () => {
  jobTitleInput.classList.remove("field-error");
  saveJobDraft();
});
jobDescriptionInput.addEventListener("input", () => {
  jobDescriptionInput.classList.remove("field-error");
  saveJobDraft();
});

// ---------- Saved job descriptions (server-side, shared across sessions) ----------

function truncate(text, max) {
  return text.length > max ? text.slice(0, max).trim() + "..." : text;
}

function formatSavedJobLabel(job) {
  // Avoid a redundant "Machine Learning -- Machine Learning Job Description..."
  // style label when the JD text already starts with the role title.
  const title = (job.title || "").trim();
  const description = (job.description || "").trim();
  const preview = truncate(description, 50);
  const descriptionAlreadyStatesTitle = title && description.toLowerCase().startsWith(title.toLowerCase());
  return descriptionAlreadyStatesTitle ? preview : `${title} -- ${preview}`;
}

async function loadSavedJobs(selectId) {
  try {
    const res = await fetch("/api/jobs");
    const data = await res.json();
    savedJobs = data.jobs || [];
  } catch (err) {
    return; // saved-job list is a convenience; a failed fetch shouldn't block the app
  }

  savedJobsSelect.innerHTML = '<option value="">+ New job description</option>';
  savedJobs.forEach((job) => {
    const opt = document.createElement("option");
    opt.value = job.id;
    opt.textContent = formatSavedJobLabel(job);
    savedJobsSelect.appendChild(opt);
  });

  savedJobsSelect.value = selectId && savedJobs.some((j) => j.id === selectId) ? selectId : "";
  deleteSavedJobBtn.hidden = !savedJobsSelect.value;
}

loadSavedJobs();

savedJobsSelect.addEventListener("change", () => {
  const jobId = savedJobsSelect.value;
  if (!jobId) {
    // "+ New job description" -- start with a clean slate
    jobTitleInput.value = "";
    jobDescriptionInput.value = "";
    deleteSavedJobBtn.hidden = true;
  } else {
    const job = savedJobs.find((j) => j.id === jobId);
    if (!job) return;
    jobTitleInput.value = job.title;
    jobDescriptionInput.value = job.description;
    deleteSavedJobBtn.hidden = false;
  }
  jobTitleInput.classList.remove("field-error");
  jobDescriptionInput.classList.remove("field-error");
  saveJobDraft();
});

deleteSavedJobBtn.addEventListener("click", async () => {
  const jobId = savedJobsSelect.value;
  const job = savedJobs.find((j) => j.id === jobId);
  if (!job) return;

  const ok = await confirmAction({
    title: "Delete saved job description?",
    message: `Remove "${job.title}" from your saved job descriptions? This can't be undone.`,
    confirmLabel: "Delete",
  });
  if (!ok) return;

  try {
    await fetch(`/api/jobs/${jobId}`, { method: "DELETE" });
  } catch (err) {
    setStatus("Could not delete that saved job description.", true);
    return;
  }
  await loadSavedJobs();
});

// ---------- Ranking history (past completed analyses) ----------

async function loadHistory(selectId) {
  try {
    const res = await fetch("/api/history");
    const data = await res.json();
    historyList = data.history || [];
  } catch (err) {
    return; // history list is a convenience; a failed fetch shouldn't block the app
  }

  historyRow.hidden = historyList.length === 0;
  historySelect.innerHTML = '<option value="">View a past analysis...</option>';
  historyList.forEach((h) => {
    const when = new Date(h.timestamp).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
    const opt = document.createElement("option");
    opt.value = h.id;
    opt.textContent = `${when} -- ${h.job_title} (${h.candidate_count} candidate${h.candidate_count === 1 ? "" : "s"})`;
    historySelect.appendChild(opt);
  });

  historySelect.value = selectId && historyList.some((h) => h.id === selectId) ? selectId : "";
  deleteHistoryBtn.hidden = !historySelect.value;
}

loadHistory();

historySelect.addEventListener("change", async () => {
  const id = historySelect.value;
  deleteHistoryBtn.hidden = !id;
  if (!id) return; // "View a past analysis..." placeholder -- nothing to load

  setStatus("Loading past analysis...", false);
  try {
    const res = await fetch(`/api/history/${id}`);
    const data = await res.json();
    if (!res.ok) {
      setStatus(data.error || "Could not load that analysis.", true);
      return;
    }
    currentResults = data.results;
    jobTitleInput.value = data.job_title;
    jobDescriptionInput.value = data.job_description;
    saveJobDraft();
    renderResults(data);
    setStatus(`Loaded a past analysis from ${new Date(data.timestamp).toLocaleString()}.`, false);
  } catch (err) {
    setStatus("Could not reach the server to load that analysis.", true);
  }
});

deleteHistoryBtn.addEventListener("click", async () => {
  const id = historySelect.value;
  const h = historyList.find((x) => x.id === id);
  if (!h) return;

  const ok = await confirmAction({
    title: "Delete this saved shortlist?",
    message: `Remove the ranked shortlist for "${h.job_title}" from your history? This can't be undone.`,
    confirmLabel: "Delete",
  });
  if (!ok) return;

  try {
    await fetch(`/api/history/${id}`, { method: "DELETE" });
  } catch (err) {
    setStatus("Could not delete that history entry.", true);
    return;
  }
  await loadHistory();
});

// ---------- Reusable confirmation dialog ----------

const confirmModal = document.getElementById("confirm-modal");
const confirmTitle = document.getElementById("confirm-modal-title");
const confirmText = document.getElementById("confirm-modal-text");
const confirmOkBtn = document.getElementById("confirm-ok-btn");
const confirmCancelBtn = document.getElementById("confirm-cancel-btn");
let confirmResolver = null;

function confirmAction({ title, message, confirmLabel = "Remove" }) {
  confirmTitle.textContent = title;
  confirmText.textContent = message;
  confirmOkBtn.textContent = confirmLabel;
  confirmModal.hidden = false;
  confirmOkBtn.focus();
  return new Promise((resolve) => {
    confirmResolver = resolve;
  });
}

function closeConfirm(result) {
  confirmModal.hidden = true;
  if (confirmResolver) {
    confirmResolver(result);
    confirmResolver = null;
  }
}

confirmOkBtn.addEventListener("click", () => closeConfirm(true));
confirmCancelBtn.addEventListener("click", () => closeConfirm(false));
confirmModal.addEventListener("click", (e) => {
  if (e.target === confirmModal) closeConfirm(false);
});

// ---------- File selection ----------

dropzone.addEventListener("click", () => fileInput.click());
dropzone.addEventListener("keydown", (e) => {
  if (e.key === "Enter" || e.key === " ") {
    e.preventDefault();
    fileInput.click();
  }
});

dropzone.addEventListener("dragover", (e) => {
  e.preventDefault();
  dropzone.classList.add("drag-over");
});
dropzone.addEventListener("dragleave", () => dropzone.classList.remove("drag-over"));
dropzone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropzone.classList.remove("drag-over");
  addFiles(e.dataTransfer.files);
});

fileInput.addEventListener("change", () => {
  addFiles(fileInput.files);
  fileInput.value = ""; // allow re-selecting the same file later
});

function addFiles(fileArrayLike) {
  let rejected = 0;
  for (const f of fileArrayLike) {
    const ext = f.name.split(".").pop().toLowerCase();
    if (ext !== "pdf" && ext !== "docx") {
      rejected++;
      continue;
    }
    selectedFiles.push(f);
  }
  if (rejected > 0) {
    setStatus(`${rejected} file(s) skipped -- only PDF and DOCX are supported.`, true);
  }
  renderFileList();
}

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function renderFileList() {
  fileListEl.innerHTML = "";
  const hasFiles = selectedFiles.length > 0;
  fileListHeader.hidden = !hasFiles;
  fileCountLabel.textContent = `${selectedFiles.length} file${selectedFiles.length === 1 ? "" : "s"} selected`;

  selectedFiles.forEach((f, idx) => {
    const li = document.createElement("li");
    li.innerHTML = `
      ${ICONS.file}
      <span class="file-name" title="${f.name}">${f.name}</span>
      <span class="file-size">${formatBytes(f.size)}</span>
      <button type="button" class="remove-btn" aria-label="Remove ${f.name}">${ICONS.trash}</button>
    `;
    li.querySelector(".remove-btn").addEventListener("click", async (e) => {
      e.stopPropagation();
      const ok = await confirmAction({
        title: "Remove file?",
        message: `Remove "${f.name}" from the upload list?`,
        confirmLabel: "Remove",
      });
      if (!ok) return;
      selectedFiles.splice(idx, 1);
      renderFileList();
    });
    fileListEl.appendChild(li);
  });
}

clearFilesBtn.addEventListener("click", async () => {
  const ok = await confirmAction({
    title: "Clear all files?",
    message: `This removes all ${selectedFiles.length} selected file(s) from the upload list.`,
    confirmLabel: "Clear all",
  });
  if (!ok) return;
  selectedFiles = [];
  renderFileList();
});

// ---------- Analyze ----------

analyzeBtn.addEventListener("click", async () => {
  const jobDescription = jobDescriptionInput.value.trim();
  const jobTitle = jobTitleInput.value.trim() || "Untitled Role";

  jobDescriptionInput.classList.remove("field-error");

  if (!jobDescription) {
    setStatus("Please paste a job description first.", true);
    jobDescriptionInput.classList.add("field-error");
    jobDescriptionInput.focus();
    return;
  }
  if (selectedFiles.length === 0) {
    setStatus("Please add at least one resume (PDF or DOCX).", true);
    dropzone.focus();
    return;
  }

  const formData = new FormData();
  formData.append("job_description", jobDescription);
  formData.append("job_title", jobTitle);
  selectedFiles.forEach((f) => formData.append("resumes", f));

  setLoading(true);
  showSkeletonRows(Math.min(selectedFiles.length, 5));
  setStatus(`Analyzing ${selectedFiles.length} resume(s)...`, false);

  try {
    const res = await fetch("/api/analyze", { method: "POST", body: formData });
    const data = await res.json();

    if (!res.ok) {
      setStatus(data.error || "Something went wrong.", true);
      resultsTableWrap.hidden = true;
      return;
    }

    currentResults = data.results;
    renderResults(data);
    setStatus(
      `Done in ${data.processing_time_seconds}s. ${data.results.length} candidate(s) ranked` +
      (data.errors.length ? `, ${data.errors.length} file(s) skipped.` : "."),
      data.errors.length > 0
    );
    await loadSavedJobs(data.saved_job_id);
    await loadHistory(data.history_id);
  } catch (err) {
    setStatus("Could not reach the server. Is the Flask app running?", true);
    resultsTableWrap.hidden = true;
  } finally {
    setLoading(false);
  }
});

function setLoading(isLoading) {
  analyzeBtn.disabled = isLoading;
  analyzeBtnLabel.textContent = isLoading ? "Analyzing..." : "Rank Candidates";
  const icon = analyzeBtn.querySelector("svg");
  if (isLoading) {
    icon.outerHTML = ICONS.spinner;
  } else {
    icon.outerHTML = '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M13 2 3 14h7l-1 8 10-12h-7l1-8z"/></svg>';
  }
}

function showSkeletonRows(count) {
  emptyState.hidden = true;
  resultsTableWrap.hidden = false;
  resultsBody.innerHTML = "";
  for (let i = 0; i < Math.max(count, 3); i++) {
    const tr = document.createElement("tr");
    tr.className = "skeleton-row";
    tr.innerHTML = `<td colspan="7"><div class="skeleton-bar" style="width:${85 - i * 6}%"></div></td>`;
    resultsBody.appendChild(tr);
  }
}

function setStatus(msg, isError) {
  statusLine.classList.add("visible");
  statusLine.classList.toggle("error", !!isError);
  statusLine.classList.toggle("success", !isError);
  statusLine.innerHTML = `${isError ? ICONS.alert : ICONS.check}<span>${msg}</span>`;
}

// ---------- Rendering ----------

function renderResults(data) {
  emptyState.hidden = true;
  resultsActions.hidden = false;
  resultsTableWrap.hidden = false;
  metaLine.hidden = false;
  metaLine.innerHTML =
    `${ICONS.info}<span><strong>${data.job_title}</strong> &mdash; JD skills detected: ${data.jd_skills.length ? data.jd_skills.join(", ") : "none detected"}</span>`;

  jdRecap.hidden = false;
  jdRecapText.textContent = data.job_description !== undefined ? data.job_description : jobDescriptionInput.value.trim();

  minScoreSelect.value = "0"; // don't let a filter from a previous run hide this run's results
  selectedForCompare.clear();
  updateCompareBar();

  document.getElementById("results-title").textContent = `Ranked Shortlist (${data.results.length})`;
  drawTable(currentResults);
}

function scoreClass(score) {
  if (score >= 70) return "score-high";
  if (score >= 45) return "score-mid";
  return "score-low";
}

function drawTable(rows) {
  resultsBody.innerHTML = "";

  if (rows.length === 0) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td colspan="7" class="muted-note" style="text-align:center;padding:24px;">No candidates match your search or score filter.</td>`;
    resultsBody.appendChild(tr);
    return;
  }

  rows.forEach((r, i) => {
    const tr = document.createElement("tr");
    tr.style.animationDelay = `${Math.min(i, 8) * 0.03}s`;

    const topSkills = r.matched_skills.slice(0, 3)
      .map((s) => `<span class="skill-chip">${s}</span>`).join("") || "<span class='muted-note'>none matched</span>";

    const bestMatchBadge = r.rank === 1
      ? `<span class="best-match-badge">${ICONS.star} Best Match</span>`
      : "";

    tr.innerHTML = `
      <td class="compare-cell"><input type="checkbox" class="compare-checkbox" data-rank="${r.rank}" ${selectedForCompare.has(String(r.rank)) ? "checked" : ""} aria-label="Select ${r.candidate_name} for comparison"></td>
      <td class="rank-cell">${r.rank}</td>
      <td><div class="candidate-cell"><span class="candidate-name">${r.candidate_name}</span>${bestMatchBadge}</div></td>
      <td><span class="score-pill ${scoreClass(r.final_score)}">${Math.round(r.final_score)}%</span></td>
      <td>${r.experience_years !== null ? r.experience_years + " yrs" : "N/A"}</td>
      <td>${topSkills}</td>
      <td><button class="view-btn" data-rank="${r.rank}">${ICONS.eye} View</button></td>
    `;
    resultsBody.appendChild(tr);
  });

  document.querySelectorAll(".view-btn").forEach((btn) => {
    btn.addEventListener("click", () => openDetail(btn.dataset.rank));
  });
  document.querySelectorAll(".compare-checkbox").forEach((cb) => {
    cb.addEventListener("change", () => toggleCompareSelection(cb));
  });
}

// ---------- Compare selected candidates ----------

function toggleCompareSelection(checkbox) {
  const rank = checkbox.dataset.rank;
  if (checkbox.checked) {
    if (selectedForCompare.size >= 3) {
      checkbox.checked = false;
      setStatus("You can compare up to 3 candidates at a time -- deselect one first.", true);
      return;
    }
    selectedForCompare.add(rank);
  } else {
    selectedForCompare.delete(rank);
  }
  updateCompareBar();
}

function updateCompareBar() {
  const n = selectedForCompare.size;
  compareBar.hidden = n === 0;
  compareCountLabel.textContent = `${n} selected (max 3)`;
  compareBtn.disabled = n < 2;
}

compareClearBtn.addEventListener("click", () => {
  selectedForCompare.clear();
  document.querySelectorAll(".compare-checkbox").forEach((cb) => (cb.checked = false));
  updateCompareBar();
});

function buildCompareTable(rows) {
  const metrics = [
    { label: "Final match score", get: (r) => `${Math.round(r.final_score)}%` },
    { label: "Semantic similarity", get: (r) => `${r.breakdown.semantic}%` },
    { label: "Keyword similarity", get: (r) => `${r.breakdown.tfidf}%` },
    { label: "Skill overlap", get: (r) => `${r.breakdown.skill_overlap}%` },
    { label: "Experience match", get: (r) => `${r.breakdown.experience}%` },
    { label: "Experience (years)", get: (r) => (r.experience_years !== null ? r.experience_years : "N/A") },
    { label: "Matched skills", get: (r) => (r.matched_skills.length ? r.matched_skills.join(", ") : "None") },
    { label: "Missing skills", get: (r) => (r.missing_skills.length ? r.missing_skills.join(", ") : "None") },
    { label: "Education", get: (r) => (r.education.length ? r.education.join(", ") : "None detected") },
  ];

  const headerCells = rows.map((r) => `<th scope="col">${r.candidate_name}${r.rank === 1 ? " " + ICONS.star : ""}</th>`).join("");
  const bodyRows = metrics.map((m) => `
    <tr>
      <th scope="row">${m.label}</th>
      ${rows.map((r) => `<td>${m.get(r)}</td>`).join("")}
    </tr>
  `).join("");

  return `
    <h3 id="modal-candidate-name">Compare Candidates</h3>
    <p class="modal-score">${rows.length} candidates side by side</p>
    <div class="table-scroll">
      <table class="compare-table">
        <thead><tr><th scope="col"></th>${headerCells}</tr></thead>
        <tbody>${bodyRows}</tbody>
      </table>
    </div>
  `;
}

compareBtn.addEventListener("click", () => {
  const rows = currentResults.filter((r) => selectedForCompare.has(String(r.rank)));
  if (rows.length < 2) return;
  modalContent.innerHTML = buildCompareTable(rows);
  modalBox.classList.add("modal-wide");
  modalOverlay.hidden = false;
  modalClose.focus();
});

// ---------- Search & sort ----------

function applySearchAndSort() {
  const query = searchBox.value.trim().toLowerCase();
  const minScore = parseInt(minScoreSelect.value, 10) || 0;
  let rows = currentResults.filter(
    (r) => r.candidate_name.toLowerCase().includes(query) && r.final_score >= minScore
  );

  const sortMode = sortSelect.value;
  if (sortMode === "score-desc") rows.sort((a, b) => b.final_score - a.final_score);
  if (sortMode === "score-asc") rows.sort((a, b) => a.final_score - b.final_score);
  if (sortMode === "name-asc") rows.sort((a, b) => a.candidate_name.localeCompare(b.candidate_name));

  drawTable(rows);
}

searchBox.addEventListener("input", applySearchAndSort);
sortSelect.addEventListener("change", applySearchAndSort);
minScoreSelect.addEventListener("change", applySearchAndSort);

// ---------- Explainability modal ----------

function openDetail(rank) {
  const r = currentResults.find((c) => String(c.rank) === String(rank));
  if (!r) return;

  const matchedHtml = r.matched_skills.length
    ? r.matched_skills.map((s) => `<span class="skill-chip">${s}</span>`).join("")
    : "<span class='muted-note'>None</span>";

  const missingHtml = r.missing_skills.length
    ? r.missing_skills.map((s) => `<span class="skill-chip missing">${s}</span>`).join("")
    : "<span class='muted-note'>None -- all required skills found</span>";

  modalContent.innerHTML = `
    <h3 id="modal-candidate-name">${r.candidate_name}</h3>
    <p class="modal-score">${Math.round(r.final_score)}% match</p>

    <div class="breakdown-row"><span>Semantic similarity (Sentence-BERT)</span><span>${r.breakdown.semantic}%</span></div>
    <div class="breakdown-row"><span>Keyword similarity (TF-IDF)</span><span>${r.breakdown.tfidf}%</span></div>
    <div class="breakdown-row"><span>Skill overlap</span><span>${r.breakdown.skill_overlap}%</span></div>
    <div class="breakdown-row"><span>Experience match</span><span>${r.breakdown.experience}%</span></div>

    <div class="skill-block">
      <h4>Matched skills</h4>
      ${matchedHtml}
    </div>
    <div class="skill-block">
      <h4>Missing skills</h4>
      ${missingHtml}
    </div>
    <div class="skill-block">
      <h4>Education detected</h4>
      <p class="muted-note">${r.education.length ? r.education.join(", ") : "None detected"}</p>
    </div>
  `;

  modalOverlay.hidden = false;
  modalClose.focus();
}

function closeModal() {
  modalOverlay.hidden = true;
  modalBox.classList.remove("modal-wide");
}

modalClose.addEventListener("click", closeModal);
modalOverlay.addEventListener("click", (e) => {
  if (e.target === modalOverlay) closeModal();
});
document.addEventListener("keydown", (e) => {
  if (e.key !== "Escape") return;
  if (!modalOverlay.hidden) closeModal();
  if (!confirmModal.hidden) closeConfirm(false);
});

// ---------- Exports ----------

document.getElementById("export-csv").addEventListener("click", () => {
  window.location.href = "/api/export/csv";
});
document.getElementById("export-pdf").addEventListener("click", () => {
  window.location.href = "/api/export/pdf";
});
