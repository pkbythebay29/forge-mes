const el = (id) => document.getElementById(id);

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
  el("equipment").textContent = JSON.stringify(equipment, null, 2);
}

async function loadBatch() {
  const batchId = el("active-batch-id").value;
  const payload = await api(`/batches/${batchId}`);
  el("batch-details").textContent = JSON.stringify(payload.batch, null, 2);
  renderInstructions(payload.recipe_version.instructions);
  el("events").innerHTML = "";
  payload.events.slice().reverse().forEach(pushEvent);
}

el("create-batch").onclick = async () => {
  const payload = await api("/batches", {
    method: "POST",
    body: JSON.stringify({
      batch_number: el("batch-number").value,
      recipe_id: Number(el("recipe-id").value),
      product_name: el("product-name").value,
      planned_quantity: Number(el("planned-qty").value),
      actor: el("sig-user").value,
    }),
  });
  el("active-batch-id").value = payload.id;
  await loadBatch();
};

el("start-batch").onclick = async () => {
  await api(`/batches/${el("active-batch-id").value}/start`, {
    method: "POST",
    body: JSON.stringify({
      actor: el("sig-user").value,
      signature: signature(),
      comment: "Operator started batch",
    }),
  });
  await loadBatch();
};

el("complete-batch").onclick = async () => {
  await api(`/batches/${el("active-batch-id").value}/complete`, {
    method: "POST",
    body: JSON.stringify({
      actor: el("sig-user").value,
      signature: signature(),
      comment: "Operator completed batch",
    }),
  });
  await loadBatch();
};

el("log-step").onclick = async () => {
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
  await loadBatch();
};

el("record-material").onclick = async () => {
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
  await loadBatch();
};

el("refresh-batch").onclick = loadBatch;

const eventSocket = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws/events`);
eventSocket.onmessage = (message) => {
  const data = JSON.parse(message.data);
  pushEvent(data.event || data);
};

const equipmentSocket = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws/equipment`);
equipmentSocket.onmessage = () => refreshEquipment();

refreshEquipment();
loadBatch().catch(() => {});
