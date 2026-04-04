const visual = (id) => document.getElementById(id);

async function visualApi(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json();
}

function setVisualizerStatus(message, tone = "info") {
  const node = visual("visualizer-status");
  node.textContent = message;
  node.dataset.tone = tone;
}

function renderHistoryTable(rows) {
  const body = document.querySelector("#history-table tbody");
  body.innerHTML = rows.map((row) => `
    <tr>
      <td>${row.batch_number}</td>
      <td>${row.status}</td>
      <td>${row.recipe_name} (${row.recipe_id})</td>
      <td>v${row.recipe_version} / ${row.recipe_version_id}</td>
      <td>${row.material_count}</td>
      <td>${row.event_count}</td>
      <td>${row.anchor_verified === null ? "Pending" : row.anchor_verified ? "Verified" : "Mismatch"}</td>
      <td>${row.created_at}</td>
      <td><button class="table-button" data-batch-id="${row.batch_id}">Load</button></td>
    </tr>
  `).join("");
  document.querySelectorAll("[data-batch-id]").forEach((button) => {
    button.onclick = () => {
      visual("timeline-batch-id").value = button.dataset.batchId;
      loadTimeline();
    };
  });
}

function renderTimelineGraph(payload) {
  const graph = visual("timeline-graph");
  graph.innerHTML = payload.timeline.map((event) => `
    <div class="timeline-node">
      <div class="timeline-dot"></div>
      <div class="timeline-card">
        <strong>${event.action}</strong>
        <span>${event.timestamp}</span>
        <span>${event.step_title || event.event_type}</span>
        <span>${event.actor}</span>
      </div>
    </div>
  `).join("");
}

function renderTimelineTable(payload) {
  const body = document.querySelector("#timeline-table tbody");
  body.innerHTML = payload.timeline.map((event) => `
    <tr>
      <td>${event.timestamp}</td>
      <td>${event.action}</td>
      <td>${event.actor}</td>
      <td>${event.step_title || ""}</td>
      <td>${event.electronic_signature ? "Yes" : "No"}</td>
      <td><code>${event.event_hash}</code></td>
    </tr>
  `).join("");
}

function renderTimelineSummary(payload) {
  const verification = payload.verification;
  visual("timeline-summary").innerHTML = `
    <strong>Batch ${payload.batch.batch_number}</strong>
    <p>Status: ${payload.batch.status}</p>
    <p>Recipe: ${payload.recipe.name} (ID ${payload.recipe.id})</p>
    <p>Version: v${payload.recipe_version.version} (ID ${payload.recipe_version.id})</p>
    <p>Verification: ${verification ? (verification.verified ? "verified" : "mismatch detected") : "no anchor yet"}</p>
  `;
}

async function refreshHistory() {
  const rows = await visualApi("/analytics/batches");
  renderHistoryTable(rows);
  setVisualizerStatus(`Loaded ${rows.length} batches from the SQL history table.`, "success");
}

async function loadTimeline() {
  const batchId = visual("timeline-batch-id").value;
  if (!batchId) {
    setVisualizerStatus("Enter or select a batch ID before loading the timeline.", "error");
    return;
  }
  const payload = await visualApi(`/batches/${batchId}/timeline`);
  renderTimelineSummary(payload);
  renderTimelineGraph(payload);
  renderTimelineTable(payload);
  setVisualizerStatus(`Timeline loaded for batch ${payload.batch.batch_number}.`, "success");
}

visual("refresh-history").onclick = () => {
  refreshHistory().catch((error) => {
    setVisualizerStatus(`History refresh failed: ${error.message}`, "error");
  });
};

visual("load-timeline").onclick = () => {
  loadTimeline().catch((error) => {
    setVisualizerStatus(`Timeline load failed: ${error.message}`, "error");
  });
};

refreshHistory().catch((error) => {
  setVisualizerStatus(`History refresh failed: ${error.message}`, "error");
});
