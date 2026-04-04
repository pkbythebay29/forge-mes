const field = (id) => document.getElementById(id);

async function configApi(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json();
}

function setConfigStatus(message, tone = "info") {
  const node = field("config-status");
  node.textContent = message;
  node.dataset.tone = tone;
}

function renderTagRows(tableId, rows) {
  const body = document.querySelector(`#${tableId} tbody`);
  body.innerHTML = rows.map((row) => `
    <tr>
      <td><input value="${row.mes_field || ""}" data-key="mes_field"></td>
      <td><input value="${row.source_tag || ""}" data-key="source_tag"></td>
      <td><input value="${row.type || "string"}" data-key="type"></td>
      <td><input value="${row.direction || "read"}" data-key="direction"></td>
      <td><input value="${row.meaning || ""}" data-key="meaning"></td>
    </tr>
  `).join("");
}

function collectTagRows(tableId) {
  return Array.from(document.querySelectorAll(`#${tableId} tbody tr`)).map((row) => {
    const item = {};
    row.querySelectorAll("input").forEach((input) => {
      item[input.dataset.key] = input.value.trim();
    });
    return item;
  }).filter((row) => row.mes_field && row.source_tag);
}

function appendEmptyTagRow(tableId, defaultDirection) {
  const body = document.querySelector(`#${tableId} tbody`);
  const row = document.createElement("tr");
  row.innerHTML = `
    <td><input value="" data-key="mes_field"></td>
    <td><input value="" data-key="source_tag"></td>
    <td><input value="string" data-key="type"></td>
    <td><input value="${defaultDirection}" data-key="direction"></td>
    <td><input value="" data-key="meaning"></td>
  `;
  body.appendChild(row);
}

async function loadDriverConfig(driverType) {
  return configApi(`/drivers/${driverType}/config`);
}

function populateOpcua(config) {
  field("opcua-endpoint").value = config.endpoint || "";
  field("opcua-namespace").value = config.metadata.namespace || "";
  field("opcua-security-mode").value = config.metadata.security_mode || "";
  field("opcua-authentication").value = config.metadata.authentication || "";
  field("opcua-username").value = config.metadata.username || "";
  field("opcua-password").value = config.metadata.password || "";
  renderTagRows("opcua-tag-table", config.tag_map || []);
}

function populateMqtt(config) {
  field("mqtt-endpoint").value = config.endpoint || "";
  field("mqtt-client-id").value = config.metadata.client_id || "";
  field("mqtt-qos").value = config.metadata.qos || "";
  field("mqtt-username").value = config.metadata.username || "";
  field("mqtt-password").value = config.metadata.password || "";
  renderTagRows("mqtt-tag-table", config.tag_map || []);
}

async function saveDriverConfig(driverType, payload, successMessage) {
  await configApi(`/drivers/${driverType}/config`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
  setConfigStatus(successMessage, "success");
}

async function saveTagMap(driverType, tableId, successMessage) {
  await configApi(`/drivers/${driverType}/tag-map`, {
    method: "PUT",
    body: JSON.stringify({ tag_map: collectTagRows(tableId) }),
  });
  setConfigStatus(successMessage, "success");
}

async function connectDriver(driverType, endpoint, successMessage) {
  await configApi(`/drivers/${driverType}/connect`, {
    method: "POST",
    body: JSON.stringify({ endpoint }),
  });
  setConfigStatus(successMessage, "success");
}

async function initializeConfiguration() {
  const [opcua, mqtt] = await Promise.all([loadDriverConfig("opcua"), loadDriverConfig("mqtt")]);
  populateOpcua(opcua);
  populateMqtt(mqtt);
}

field("save-opcua-config").onclick = async () => {
  try {
    await saveDriverConfig("opcua", {
      endpoint: field("opcua-endpoint").value,
      metadata: {
        namespace: field("opcua-namespace").value,
        security_mode: field("opcua-security-mode").value,
        authentication: field("opcua-authentication").value,
        username: field("opcua-username").value,
        password: field("opcua-password").value,
      },
    }, "OPC UA configuration updated.");
  } catch (error) {
    setConfigStatus(`OPC UA config update failed: ${error.message}`, "error");
  }
};

field("connect-opcua-config").onclick = async () => {
  try {
    await connectDriver("opcua", field("opcua-endpoint").value, "OPC UA driver connected using the current configuration.");
  } catch (error) {
    setConfigStatus(`OPC UA connect failed: ${error.message}`, "error");
  }
};

field("save-opcua-tags").onclick = async () => {
  try {
    await saveTagMap("opcua", "opcua-tag-table", "OPC UA tag map saved.");
  } catch (error) {
    setConfigStatus(`OPC UA tag map update failed: ${error.message}`, "error");
  }
};

field("add-opcua-tag").onclick = () => appendEmptyTagRow("opcua-tag-table", "read");

field("save-mqtt-config").onclick = async () => {
  try {
    await saveDriverConfig("mqtt", {
      endpoint: field("mqtt-endpoint").value,
      metadata: {
        client_id: field("mqtt-client-id").value,
        qos: field("mqtt-qos").value,
        username: field("mqtt-username").value,
        password: field("mqtt-password").value,
      },
    }, "MQTT configuration updated.");
  } catch (error) {
    setConfigStatus(`MQTT config update failed: ${error.message}`, "error");
  }
};

field("connect-mqtt-config").onclick = async () => {
  try {
    await connectDriver("mqtt", field("mqtt-endpoint").value, "MQTT driver connected using the current configuration.");
  } catch (error) {
    setConfigStatus(`MQTT connect failed: ${error.message}`, "error");
  }
};

field("save-mqtt-tags").onclick = async () => {
  try {
    await saveTagMap("mqtt", "mqtt-tag-table", "MQTT tag map saved.");
  } catch (error) {
    setConfigStatus(`MQTT tag map update failed: ${error.message}`, "error");
  }
};

field("add-mqtt-tag").onclick = () => appendEmptyTagRow("mqtt-tag-table", "subscribe");

initializeConfiguration().catch((error) => {
  setConfigStatus(`Configuration load failed: ${error.message}`, "error");
});
