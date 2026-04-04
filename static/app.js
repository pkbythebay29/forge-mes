const el = (id) => document.getElementById(id);
let currentBatch = null;
let currentRecipeStepCount = 0;
let availableRecipes = [];

function signature() {
  return {
    username: el("sig-user").value,
    password: el("sig-pass").value,
  };
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    const error = await response.text();
    throw new Error(error);
  }
  return response.json();
}

function renderPills(id, items = []) {
  el(id).innerHTML = items.map((item) => `<div class="pill"><span>Suggested action</span><strong>${item}</strong></div>`).join("");
}

function setStatus(message, tone = "info") {
  const node = el("action-status");
  node.textContent = message;
  node.dataset.tone = tone;
}

function addUiAuditNotice(action, detail) {
  pushEvent({
    kind: "ui_notice",
    action,
    actor: "ui",
    created_at: new Date().toISOString(),
    payload: { detail },
  });
}

function renderBatchSummary(batch) {
  el("batch-details").textContent = [
    `Batch ${batch.batch_number}`,
    `Status: ${batch.status}`,
    `Product: ${batch.product_name}`,
    `Planned quantity: ${batch.planned_quantity}`,
    `Actual quantity: ${batch.actual_quantity}`,
    `Current step: ${batch.current_step}`,
    `Started at: ${batch.started_at || "not started"}`,
    `Completed at: ${batch.completed_at || "not completed"}`,
  ].join("\n");
}

function updateProductFromRecipe() {
  const recipe = availableRecipes.find((item) => item.recipe.id === Number(el("recipe-id").value));
  if (recipe && !el("product-name").dataset.userEdited) {
    el("product-name").value = recipe.recipe.name;
  }
}

function renderRecipeVersions(recipeId) {
  const versionSelect = el("recipe-version-id");
  const recipe = availableRecipes.find((item) => item.recipe.id === Number(recipeId));
  versionSelect.innerHTML = "";
  if (!recipe) {
    versionSelect.innerHTML = `<option value="">No approved version</option>`;
    return;
  }
  const latest = recipe.latest_version;
  versionSelect.innerHTML = `<option value="${latest.id}">v${latest.version} (${latest.status})</option>`;
  updateProductFromRecipe();
}

async function loadRecipes() {
  availableRecipes = await api("/recipes");
  const select = el("recipe-id");
  select.innerHTML = availableRecipes
    .map((item) => `<option value="${item.recipe.id}">${item.recipe.name} - latest v${item.latest_version.version}</option>`)
    .join("");
  if (availableRecipes.length) {
    renderRecipeVersions(select.value || availableRecipes[0].recipe.id);
  }
}

function renderGenealogySummary(payload) {
  const box = el("genealogy-summary");
  if (!box) return;
  if (!payload?.batch || !payload?.recipe || !payload?.recipe_version) {
    box.innerHTML = `
      <strong>Genealogy Context</strong>
      <p>Load a batch to see how recorded material lots connect to the batch, recipe, and approved recipe version.</p>
    `;
    return;
  }
  const materialCount = payload.materials?.length || 0;
  const lots = materialCount
    ? payload.materials.map((material) => `${material.lot_number} (${material.material_code})`).join(", ")
    : "No material lots recorded yet.";
  box.innerHTML = `
    <strong>Genealogy Context</strong>
    <p><strong>Batch</strong>: ${payload.batch.batch_number}</p>
    <p><strong>Recipe</strong>: ${payload.recipe.name}</p>
    <p><strong>Approved Version</strong>: v${payload.recipe_version.version}</p>
    <p><strong>Material Lots</strong>: ${materialCount}</p>
    <p>${lots}</p>
  `;
}

function setButtonState(id, enabled) {
  const node = el(id);
  if (!node) return;
  node.disabled = !enabled;
}

function updateActionAvailability(batch) {
  const hasBatch = Boolean(batch?.id);
  const inProgress = batch?.status === "in_progress";
  const created = batch?.status === "created";
  const completed = batch?.status === "completed";
  const stepReady = inProgress && batch.current_step <= currentRecipeStepCount;
  const completeReady = inProgress && currentRecipeStepCount > 0 && batch.current_step > currentRecipeStepCount;

  setButtonState("refresh-batch", hasBatch);
  setButtonState("start-batch", created);
  setButtonState("complete-batch", completeReady);
  setButtonState("log-step", stepReady);
  setButtonState("record-material", hasBatch && !completed && batch.status !== "created");
  setButtonState("verify-batch", completed);
  setButtonState("export-batch-pdf", hasBatch);
  setButtonState("tamper-batch", completed);
}

async function suggestNextBatchNumber() {
  const batches = await api("/batches");
  const numbers = batches
    .map((batch) => Number(String(batch.batch_number).replace(/^B-/, "")))
    .filter((value) => Number.isFinite(value));
  const next = (numbers.length ? Math.max(...numbers) : 1000) + 1;
  el("batch-number").value = `B-${next}`;
}

function pushEvent(entry) {
  const wrapper = document.createElement("div");
  wrapper.className = "event";
  wrapper.innerHTML = `<strong>${entry.action || entry.kind}</strong><br>${entry.actor || ""} ${entry.created_at || ""}<br><code>${JSON.stringify(entry.payload || entry.event || entry, null, 2)}</code>`;
  el("events").prepend(wrapper);
}

function renderInstructions(instructions = []) {
  const box = el("instructions");
  box.innerHTML = "";
  instructions.forEach((step) => {
    const node = document.createElement("div");
    node.className = "instruction-step";
    node.innerHTML = `<strong>Step ${step.step}: ${step.title}</strong><br>${step.instruction}<br>Target: ${step.target_value ?? "n/a"}`;
    box.appendChild(node);
  });
}

async function refreshEquipment() {
  const equipment = await api("/equipment");
  el("equipment").textContent = equipment.map((item) => [
    `${item.name} (${item.equipment_code})`,
    `Status: ${item.status}`,
    `Availability: ${item.availability}`,
    `Performance: ${item.performance}`,
    `Quality: ${item.quality}`,
    `OEE: ${item.oee}`,
    `Good count: ${item.good_count}`,
    `Reject count: ${item.reject_count}`,
  ].join("\n")).join("\n\n");
}

async function refreshAnchors() {
  const anchors = await api("/anchors");
  el("anchor-count").textContent = anchors.length;
}

async function refreshDrivers() {
  const drivers = await api("/drivers");
  el("driver-count").textContent = drivers.length;
  el("drivers").innerHTML = drivers.map((driver) => `
    <div class="driver-item">
      <strong>${driver.name}</strong><br>
      ${driver.protocol} | ${driver.status}<br>
      <code>${driver.endpoint}</code><br>
      <span>${driver.status === "connected" ? "Tag mappings can now bind incoming industrial data to MES fields." : "Not yet connected to a live endpoint."}</span>
    </div>
  `).join("");
}

async function loadBatch() {
  const batchId = el("active-batch-id").value;
  if (!availableRecipes.length) {
    await loadRecipes();
  }
  const payload = await api(`/batches/${batchId}`);
  currentBatch = payload.batch;
  currentRecipeStepCount = payload.recipe_version.instructions.length;
  el("recipe-id").value = String(payload.recipe.id);
  renderRecipeVersions(payload.recipe.id);
  el("recipe-version-id").value = String(payload.recipe_version.id);
  el("product-name").value = payload.batch.product_name;
  renderBatchSummary(payload.batch);
  renderInstructions(payload.recipe_version.instructions);
  renderGenealogySummary(payload);
  updateActionAvailability(payload.batch);
  el("events").innerHTML = "";
  payload.events.slice().reverse().forEach(pushEvent);
  await renderVerificationState();
  await askAgent();
  setStatus(`Loaded batch ${payload.batch.batch_number}.`);
}

el("create-batch").onclick = async () => {
  try {
    const payload = await api("/batches", {
      method: "POST",
      body: JSON.stringify({
        batch_number: el("batch-number").value,
        recipe_id: Number(el("recipe-id").value),
        recipe_version_id: el("recipe-version-id").value ? Number(el("recipe-version-id").value) : null,
        product_name: el("product-name").value,
        planned_quantity: Number(el("planned-qty").value),
        actor: el("sig-user").value,
      }),
    });
    el("active-batch-id").value = payload.id;
    currentBatch = payload;
    setStatus(`Created batch ${payload.batch_number}.`, "success");
    await suggestNextBatchNumber();
    await loadBatch();
  } catch (error) {
    setStatus(`Create Batch failed: ${error.message}`, "error");
    addUiAuditNotice("create_batch_failed", error.message);
  }
};

el("start-batch").onclick = async () => {
  try {
    await api(`/batches/${el("active-batch-id").value}/start`, {
      method: "POST",
      body: JSON.stringify({
        actor: el("sig-user").value,
        signature: signature(),
        comment: "Operator started batch",
      }),
    });
    setStatus("Batch started and recorded in the audit trail.", "success");
    await loadBatch();
  } catch (error) {
    setStatus(`Start failed: ${error.message}`, "error");
    addUiAuditNotice("start_batch_failed", error.message);
  }
};

el("complete-batch").onclick = async () => {
  try {
    await api(`/batches/${el("active-batch-id").value}/complete`, {
      method: "POST",
      body: JSON.stringify({
        actor: el("sig-user").value,
        signature: signature(),
        comment: "Operator completed batch",
      }),
    });
    setStatus("Batch completed, anchored, and recorded in the audit trail.", "success");
    await loadBatch();
  } catch (error) {
    setStatus(`Complete failed: ${error.message}`, "error");
    addUiAuditNotice("complete_batch_failed", error.message);
  }
};

el("log-step").onclick = async () => {
  try {
    await api("/events", {
      method: "POST",
      body: JSON.stringify({
        batch_id: Number(el("active-batch-id").value),
        event_type: "execution",
        action: "step_completed",
        actor: el("sig-user").value,
        payload: {
          step_title: el("step-title").value,
          observed_value: el("step-value").value,
        },
        signature: signature(),
        comment: "Operator confirmed step",
      }),
    });
    setStatus("Step execution logged in the audit trail.", "success");
    await loadBatch();
  } catch (error) {
    setStatus(`Step logging failed: ${error.message}`, "error");
    addUiAuditNotice("log_step_failed", error.message);
  }
};

el("record-material").onclick = async () => {
  try {
    await api("/materials", {
      method: "POST",
      body: JSON.stringify({
        material_code: el("material-code").value,
        lot_number: el("lot-number").value,
        quantity: Number(el("lot-qty").value),
        parent_lot_id: el("parent-lot-id").value ? Number(el("parent-lot-id").value) : null,
        batch_id: Number(el("active-batch-id").value),
        actor: el("sig-user").value,
      }),
    });
    setStatus("Material genealogy recorded in the audit trail.", "success");
    await loadBatch();
  } catch (error) {
    setStatus(`Material recording failed: ${error.message}`, "error");
    addUiAuditNotice("record_material_failed", error.message);
  }
};

el("recipe-id").onchange = () => {
  renderRecipeVersions(el("recipe-id").value);
  addUiAuditNotice("recipe_selection_changed", "Recipe selection changed in the form. No MES record was changed.");
  setStatus("Recipe selection updated. Create Batch will use the selected approved recipe version.");
};

el("product-name").addEventListener("input", () => {
  el("product-name").dataset.userEdited = "true";
});

async function verifyBatch() {
  if (!currentBatch || currentBatch.status !== "completed") {
    setStatus("Verification is only available after the batch is completed.", "error");
    addUiAuditNotice("verify_anchor_blocked", "Verification was blocked because the batch is not completed yet.");
    return;
  }
  await renderVerificationState(true);
  setStatus("Verification requested. See the blockchain verification panel for the current result.");
  addUiAuditNotice("verify_anchor", "Verification checks the current batch against its anchored hash. No MES record is changed by this action.");
}

async function renderVerificationState(forceVerify = false) {
  const batchId = el("active-batch-id").value;
  try {
    const verification = await api(`/anchors/batch/${batchId}`);
    el("verification").innerHTML = `
      <strong>${verification.verified ? "Anchor verified" : "Integrity mismatch detected"}</strong><br><br>
      <div><strong>tx_id</strong><br><code>${verification.tx_id}</code></div><br>
      <div><strong>stored_hash</strong><br><code>${verification.stored_hash}</code></div><br>
      <div><strong>recalculated_hash</strong><br><code>${verification.recalculated_hash}</code></div><br>
      <div>${verification.verified ? "The current batch record still matches the anchored blockchain hash." : "The current batch record no longer matches the anchored hash, so Forge flags possible tampering."}</div>
    `;
  } catch (error) {
    el("verification").innerHTML = `
      <strong>${forceVerify ? "No blockchain anchor found" : "Verification pending"}</strong><br><br>
      <div>${forceVerify ? "This batch does not have an anchored completed record yet. Complete the batch first, then verify again." : "Load or complete a batch to see its current blockchain verification state here."}</div>
    `;
  }
  await refreshAnchors();
}

async function askAgent() {
  const batchId = Number(el("active-batch-id").value);
  const response = await api("/agent/assist", {
    method: "POST",
    body: JSON.stringify({
      prompt: el("agent-prompt").value,
      batch_id: Number.isNaN(batchId) ? null : batchId,
      provider: el("agent-provider").value,
    }),
  });
  el("agent-answer").innerHTML = `
    <strong>${response.message}</strong><br><br>
    <div>Provider: ${response.provider || "builtin"}</div><br>
    ${response.reasoning.map((item) => `<div>${item}</div>`).join("")}
  `;
  renderPills("agent-actions", response.actions);
  setStatus(`Operator Assistant guidance generated using ${response.provider || "builtin"}.`);
  addUiAuditNotice("operator_assistant_requested", `Guidance generated via ${response.provider || "builtin"} provider. No MES record was changed.`);
}

el("verify-batch").onclick = verifyBatch;
el("ask-agent").onclick = askAgent;
el("tamper-batch").onclick = async () => {
  if (!currentBatch || currentBatch.status !== "completed") {
    setStatus("Tamper demo is only available after batch completion.", "error");
    addUiAuditNotice("tamper_demo_blocked", "Tamper demo was blocked because the batch is not completed yet.");
    return;
  }
  try {
    await api(`/demo/tamper/batches/${el("active-batch-id").value}`, { method: "POST" });
    setStatus("Tamper demo applied. The batch record changed, so verification should now fail.", "error");
    await loadBatch();
    await verifyBatch();
  } catch (error) {
    setStatus(`Tamper demo failed: ${error.message}`, "error");
    addUiAuditNotice("tamper_demo_failed", error.message);
  }
};

el("export-batch-pdf").onclick = () => {
  if (!currentBatch) {
    setStatus("Load a batch before exporting the eBR PDF.", "error");
    addUiAuditNotice("export_ebr_pdf_blocked", "PDF export was blocked because no batch is loaded.");
    return;
  }
  const batchId = el("active-batch-id").value;
  window.open(`/batches/${batchId}/ebr.pdf`, "_blank");
  setStatus("EBR PDF export opened. This extracts evidence but does not change MES state.");
  addUiAuditNotice("export_ebr_pdf", "PDF export requested. No MES record was changed.");
};

document.querySelectorAll("[data-driver-connect]").forEach((button) => {
  button.onclick = async () => {
    try {
      const driver = await api(`/drivers/${button.dataset.driverConnect}/connect`, {
        method: "POST",
        body: JSON.stringify({}),
      });
      setStatus(`${driver.name} connected. Driver state updated, but no batch record was changed.`);
      addUiAuditNotice("driver_connected", `${driver.name} connected at ${driver.endpoint}. No MES record was changed.`);
      await refreshDrivers();
      await askAgent();
    } catch (error) {
      setStatus(`Driver connect failed: ${error.message}`, "error");
      addUiAuditNotice("driver_connect_failed", error.message);
    }
  };
});

el("refresh-batch").onclick = async () => {
  try {
    await loadBatch();
    addUiAuditNotice("batch_loaded", "Batch view refreshed. No MES record was changed.");
  } catch (error) {
    setStatus(`Load failed: ${error.message}`, "error");
    addUiAuditNotice("batch_load_failed", error.message);
  }
};

const eventSocket = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws/events`);
eventSocket.onmessage = (message) => {
  const data = JSON.parse(message.data);
  pushEvent(data.event || data);
};

const equipmentSocket = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws/equipment`);
equipmentSocket.onmessage = () => refreshEquipment();

refreshEquipment();
refreshAnchors();
refreshDrivers();
updateActionAvailability(null);
renderGenealogySummary(null);
suggestNextBatchNumber().catch(() => {});
loadRecipes().catch(() => {
  setStatus("Recipe list could not be loaded.", "error");
});
loadBatch().catch(() => {});
