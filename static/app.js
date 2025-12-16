// ==========================
// State variables
// ==========================
let draggingBear = null;        // mouse interaction only
let draggingCastle = null;     // mouse interaction only
let mapData = null;            // hydrated from server, mutated locally for UI
let castleSort = {             // table UI concern
  key: null,
  asc: true
};

window.remoteBusy = new Set(); // sync / optimistic UI guard

const canvas = document.getElementById("map");
if (!canvas) throw new Error("Canvas #map not found");
const ctx = canvas.getContext("2d");

const TILE_SIZE = 40;
const FALLBACK_EFFICIENCY_SCALE = [
  { max: 6,  color: "#16a34a", label: "Excellent" },
  { max: 10, color: "#2563eb", label: "Good" },
  { max: 15, color: "#64748b", label: "Poor" },
  { max: Infinity, color: "#1f2937", label: "Bad" }
];

// ==========================
// Server-Sent Events (SSE)
// ==========================
let sse = null;

function initSSE() {
  if (sse) return; // prevent double-connects

  try {
    sse = new EventSource("/api/stream");

    sse.onopen = () => {
      console.log("[SSE] Connected");
    };

    sse.onerror = err => {
      console.warn("[SSE] Connection lost", err);
      // Browser will auto-retry; no manual reconnect needed
    };

    // Generic message (optional)
    sse.onmessage = evt => {
      console.log("[SSE] message:", evt.data);
    };

    // Authoritative signal: server says map data changed
sse.onmessage = async evt => {
  const msg = JSON.parse(evt.data);
  if (msg.type !== "config_update") return;

  const ok = await loadMapData();
  if (!ok) return;

  renderCastleTable();
  drawMap(mapData);
};


    // Optional: server tells us it's ready
    sse.addEventListener("server_ready", () => {
      console.log("[SSE] server_ready");
    });

  } catch (e) {
    console.error("[SSE] Failed to initialise", e);
  }
}

(async () => {
  const ok = await loadMapData();
  if (!ok) return;

  renderCastleTable();
  // drawMap(mapData);

  initSSE();

  if (window.Sync?.init) {
    Sync.init();
  }
})();

// ==========================
// Normalisation functions
// ==========================
function normaliseBear(bear, index) {
  return {
    id: bear.id ?? `Bear ${index + 1}`,
    x: typeof bear.x === "number" ? bear.x : null,
    y: typeof bear.y === "number" ? bear.y : null,
    locked: !!bear.locked
  };
}

function normaliseCastle(castle, index) {
  return {
    id: castle.id ?? `Castle ${index + 1}`,
    player: castle.player ?? "",
    power: Number(castle.power) || 0,
    player_level: Number(castle.player_level) || 0,
    command_centre_level: Number(castle.command_centre_level) || 0,
    attendance: Number(castle.attendance) || 0,
    rallies_30min: Number(castle.rallies_30min) || 0,

    preference: castle.preference ?? "both",

    current_trap: castle.current_trap ?? null,
    recommended_trap: castle.recommended_trap ?? null,

    priority: castle.priority ?? null,
    efficiency: castle.efficiency ?? null,

    x: typeof castle.x === "number" ? castle.x : null,
    y: typeof castle.y === "number" ? castle.y : null,

    locked: !!castle.locked
  };
}

function normaliseBanner(banner, index) {
  return {
    id: banner.id ?? `B${index + 1}`,
    x: typeof banner.x === "number" ? banner.x : null,
    y: typeof banner.y === "number" ? banner.y : null,
    locked: !!banner.locked
  };
}

// ==========================
// Fetch Map Data from Server
// ==========================
async function loadMapData() {
  try {
    const res = await fetch("/api/map");

    if (!res.ok) {
      throw new Error(`API /api/map failed: ${res.status}`);
    }

    const raw = await res.json();

    // ---- efficiency scale (server preferred, fallback safe) ----
    const efficiencyScale =
      Array.isArray(raw.efficiency_scale) &&
      raw.efficiency_scale.every(
        e => typeof e.max === "number" && typeof e.color === "string"
      )
        ? raw.efficiency_scale
        : FALLBACK_EFFICIENCY_SCALE;

    // ---- normalised authoritative state ----
    const config = {
      grid_size: Number(raw.grid_size) || 0,

      efficiency_scale: efficiencyScale,

      bear_traps: Array.isArray(raw.bear_traps)
        ? raw.bear_traps.map(normaliseBear)
        : [],

      castles: Array.isArray(raw.castles)
        ? raw.castles.map(normaliseCastle)
        : [],

      banners: Array.isArray(raw.banners)
        ? raw.banners.map(normaliseBanner)
        : []
    };

    mapData = config;
    window.mapData = mapData;

    return true;
  } catch (err) {
    console.error(err);
    alert("Failed to load map data from server");
    return false;
  }
}

(async () => {
  const ok = await loadMapData();
  if (!ok) return;

  renderCastleTable();
  // drawMap(mapData);

  if (window.Sync?.init) {
    Sync.init();
  }
})();


// ==========================
// Utilities
// ==========================
function escapeRegex(str) {
  return str.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function highlightText(text, query) {
  if (!query) return document.createTextNode(text);

  const regex = new RegExp(`(${escapeRegex(query)})`, "ig");
  const frag = document.createDocumentFragment();

  let lastIndex = 0;
  text.replace(regex, (match, _g, index) => {
    if (index > lastIndex) {
      frag.appendChild(document.createTextNode(text.slice(lastIndex, index)));
    }
    const mark = document.createElement("mark");
    mark.textContent = match;
    frag.appendChild(mark);
    lastIndex = index + match.length;
  });

  if (lastIndex < text.length) {
    frag.appendChild(document.createTextNode(text.slice(lastIndex)));
  }

  return frag;
}

// ==========================
// Input Builders
// ==========================
function createTextInput(value, onChange) {
  const input = document.createElement("input");
  input.type = "text";
  input.value = value ?? "";
  input.size = Math.max(input.value.length, 4);

  input.addEventListener("input", () => {
    input.size = Math.max(input.value.length, 4);
    onChange(input.value);
  });

  return input;
}

// ==========================
// Table Cell Builders
// ==========================

function tdSelect(field, obj, options) {
  const td = document.createElement("td");
  const select = document.createElement("select");

  options.forEach(o => {
    const opt = document.createElement("option");
    opt.value = o;
    opt.textContent = o;
    select.appendChild(opt);
  });

  select.value = obj[field];

  select.onchange = async () => {
    obj[field] = select.value;

    // Send the updated field to the server
    await updateCastleField(obj.id, field, obj[field]);
  };

  td.appendChild(select);
  return td;
}

function tdText(value) {
  const td = document.createElement("td");
  td.textContent = value ?? "—";
  return td;
}

function tdReadonly(value) {
  const td = document.createElement("td");
  td.textContent = value ?? "—";
  td.style.opacity = 0.6;
  return td;
}

function tdInput(field, obj) {
  const td = document.createElement("td");

  const input = createTextInput(obj[field], value => {
    obj[field] = value;

    // Update only when changes are made, don't force redraw
    updateCastleField(obj.id, field, value);
  });

  td.appendChild(input);
  return td;
}

function tdNumber(field, obj) {
  const td = document.createElement("td");
  const input = document.createElement("input");

  input.type = "number";
  input.value = obj[field] ?? 0;

  input.onchange = async () => {
    const value = Number(input.value) || 0;

    // Send the updated value to the server
    await updateCastleField(obj.id, field, value);
  };

  td.appendChild(input);
  return td;
}

function tdCheckbox(field, obj) {
const td = document.createElement("td");
td.classList.add("checkbox");
  const input = document.createElement("input");

  input.type = "checkbox";
  input.checked = !!obj[field];

  input.onchange = async () => {
    obj[field] = input.checked;

    // Send the updated field to the server
    await updateCastleField(obj.id, field, obj[field]);
  };

  td.appendChild(input);
  return td;
}

// ==========================
// Helper Functions
// ==========================
async function updateCastleField(castleId, field, value) {
  try {
    const response = await fetch("/api/castles/update", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        id: castleId,
        [field]: value,
      }),
    });

    const result = await response.json();

    if (!response.ok) {
      throw new Error(result.message || "Error updating castle");
    }

    // Inform user of successful update if needed
    console.log("Update Successful:", result);

  } catch (error) {
    console.error("Failed to update castle:", error);
    alert(`Failed to update: ${error.message}`);
  }
}

// ==========================
// Table Rendering
// ==========================

function renderCastleTable() {
  const tbody = document.getElementById("castleTableBody");
  const query = document.getElementById("castleSearch")?.value
    .trim()
    .toLowerCase();

  tbody.innerHTML = "";

  mapData.castles.forEach(c => {
    const haystack = [
      c.id,
      c.player,
      c.preference
    ].join(" ").toLowerCase();

    if (query && !haystack.includes(query)) return;

    const tr = document.createElement("tr");

    /* ID (plain text → mark highlight) */
    const idTd = document.createElement("td");
    idTd.appendChild(highlightText(c.id, query));
    tr.appendChild(idTd);

    /* Player (input → outline highlight) */
    const playerTd = tdInput("player", c);
    if (query && c.player?.toLowerCase().includes(query)) {
      playerTd.querySelector("input")?.classList.add("match-input");
    }
    tr.appendChild(playerTd);

    tr.appendChild(tdNumber("power", c));
    tr.appendChild(tdNumber("player_level", c));
    tr.appendChild(tdNumber("command_centre_level", c));
    tr.appendChild(tdNumber("attendance", c));
    tr.appendChild(tdNumber("rallies_30min", c));

    /* Preference (select → outline highlight) */
    const prefTd = tdSelect("preference", c, ["Bear 1", "Bear 2", "both"]);
    if (query && c.preference?.toLowerCase().includes(query)) {
      prefTd.querySelector("select")?.classList.add("match-input");
    }
    tr.appendChild(prefTd);

    tr.appendChild(tdCheckbox("locked", c));
    tr.appendChild(tdReadonly(c.priority));
    tr.appendChild(tdReadonly(c.efficiency));

    tbody.appendChild(tr);
  });
    enableTableSorting();
  updateSortIndicators();
}


// Function to update sort indicators (arrows) on the table header
function updateSortIndicators() {
  document.querySelectorAll("#castleTable th[data-sort]").forEach(th => {
    if (!th.dataset.label) {
      th.dataset.label = th.textContent.trim(); // Store the original header text
    }

    th.textContent = th.dataset.label; // Reset to the original label

    // Apply sort indicator (▲ or ▼)
    if (th.dataset.sort === castleSort.key) {
      th.textContent += castleSort.asc ? " ▲" : " ▼";
    }
  });
}

// Function to sort castles by the selected key (column)
function sortCastles(key) {
  if (!mapData?.castles) return; // Ensure mapData and castles are available

  // Toggle sorting direction if the same column is clicked
  if (castleSort.key === key) {
    castleSort.asc = !castleSort.asc;
  } else {
    castleSort.key = key;
    castleSort.asc = true; // Default to ascending if a new column is clicked
  }

  const dir = castleSort.asc ? 1 : -1; // 1 for ascending, -1 for descending

  // Sort the castles array based on the selected column
  mapData.castles.sort((a, b) => {
    let va = a[key];
    let vb = b[key];

    // Null values should come last
    if (va == null && vb == null) return 0;
    if (va == null) return 1;
    if (vb == null) return -1;

    // For boolean values, true > false
    if (typeof va === "boolean") return (va === vb ? 0 : va ? 1 : -1) * dir;

    // For numeric values
    if (typeof va === "number") return (va - vb) * dir;

    // For string comparison
    return va.toString().localeCompare(vb.toString()) * dir;
  });

  // Re-render table and update sort indicators
  renderCastleTable();
  updateSortIndicators();
}

// Function to enable sorting by clicking on table headers
function enableTableSorting() {
  document
    .querySelectorAll("#castleTable th[data-sort]") // Select all sortable table headers
    .forEach(th => {
      th.style.cursor = "pointer"; // Change cursor to pointer to indicate it's clickable

      // Attach an event listener to each header for sorting
      th.onclick = () => sortCastles(th.dataset.sort);
    });
}

// Enable table sorting functionality and apply initial sort indicators
enableTableSorting();
updateSortIndicators();

// // ==========================
// // Render and Placement
// // ==========================
// function getCastleTiles(castle) {
//     const tiles = [];
//     for (let dx = 0; dx < 2; dx++) {
//         for (let dy = 0; dy < 2; dy++) {
//             tiles.push({
//                 x: castle.x + dx,
//                 y: castle.y + dy
//             });
//         }
//     }
//     return tiles;
// }
//
// function screenToGrid(mouseX, mouseY) {
//     if (!mapData) return {x: 0, y: 0};
//
//     const size = mapData.grid_size;
//     const mapPixelSize = size * TILE_SIZE;
//     const center = mapPixelSize / 2;
//
//     let x = mouseX - canvas.width / 2;
//     let y = mouseY - canvas.height / 2;
//
//     const angle = -Math.PI / 4;
//     const rx = x * Math.cos(angle) - y * Math.sin(angle);
//     const ry = x * Math.sin(angle) + y * Math.cos(angle);
//
//     return {
//         x: Math.max(0, Math.min(size - 1, Math.floor((rx + center) / TILE_SIZE))),
//         y: Math.max(0, Math.min(size - 1, Math.floor((ry + center) / TILE_SIZE)))
//     };
// }
//
// function getCastleRole(castle) {
//     const pref = (castle.preference || "").toLowerCase();
//     if (pref === "bear 1") return "bear1";
//     if (pref === "bear 2") return "bear2";
//     return "both";
// }
//
// function hasPlacement(c) {
//     return c.x != null && c.y != null;
// }
//
// function drawMap(data) {
//     if (!data || !canvas || !ctx) return;
//
//     const size = data.grid_size ?? 0;
//     const banners = data.banners ?? [];
//     const bears = data.bear_traps ?? [];
//     const castles = data.castles ?? [];
//
//     const mapPixelSize = size * TILE_SIZE;
//     const center = mapPixelSize / 2;
//
//     ctx.clearRect(0, 0, canvas.width, canvas.height);
//
//     ctx.save();
//
//     // rotate around canvas centre
//     ctx.translate(canvas.width / 2, canvas.height / 2);
//     ctx.rotate(Math.PI / 4);
//     ctx.translate(-center, -center);
//
//     // -------- GRID (batched for performance) --------
//     ctx.strokeStyle = "#ccc";
//     ctx.lineWidth = 1;
//     ctx.beginPath();
//
//     for (let x = 0; x < size; x++) {
//         for (let y = 0; y < size; y++) {
//             ctx.rect(
//                 x * TILE_SIZE,
//                 y * TILE_SIZE,
//                 TILE_SIZE,
//                 TILE_SIZE
//             );
//         }
//     }
//
//     ctx.stroke();
//
//     // -------- ENTITIES --------
//     banners.forEach(b => drawBanner?.(b));
//     bears.forEach(b => drawBearTrap?.(b));
//     castles.forEach(c => drawCastle?.(c));
//
//     ctx.restore();
// }
//
// function drawBanner(banner) {
//     if (!banner || banner.x == null || banner.y == null) return;
//
//     const px = banner.x * TILE_SIZE;
//     const py = banner.y * TILE_SIZE;
//
//     ctx.fillStyle = "#1e3a8a";
//     ctx.fillRect(px, py, TILE_SIZE, TILE_SIZE);
//
//     ctx.strokeStyle = "#ffffff";
//     ctx.lineWidth = 1;
//     ctx.strokeRect(px, py, TILE_SIZE, TILE_SIZE);
//
//     ctx.save();
//     ctx.translate(px + TILE_SIZE / 2, py + TILE_SIZE / 2);
//     ctx.rotate(-Math.PI / 4);
//
//     ctx.fillStyle = "#ffffff";
//     ctx.font = `bold ${Math.max(12, TILE_SIZE * 0.35)}px sans-serif`;
//     ctx.textAlign = "center";
//     ctx.textBaseline = "middle";
//
//     ctx.fillText(String(banner.id ?? ""), 0, 0);
//     ctx.restore();
// }
//
// function drawBearTrap(bear) {
//   if (!bear || bear.x == null || bear.y == null || !mapData) return;
//
//   const gridSize = mapData.grid_size;
//   const cx = bear.x;
//   const cy = bear.y;
//
//   const isRemoteBusy =
//     window.remoteBusy?.has(bear.id) &&
//     draggingBear?.id !== bear.id;
//
//   /* ===============================
//      Influence tiles (3x3)
//   =============================== */
//   ctx.fillStyle = "rgba(120,120,120,0.35)";
//   for (let x = cx - 1; x <= cx + 1; x++) {
//     for (let y = cy - 1; y <= cy + 1; y++) {
//       if (x < 0 || y < 0 || x >= gridSize || y >= gridSize) continue;
//       ctx.fillRect(
//         x * TILE_SIZE,
//         y * TILE_SIZE,
//         TILE_SIZE,
//         TILE_SIZE
//       );
//     }
//   }
//
//   /* ===============================
//      Bear circle
//   =============================== */
//   const px = cx * TILE_SIZE + TILE_SIZE / 2;
//   const py = cy * TILE_SIZE + TILE_SIZE / 2;
//
//   // slightly smaller than 3x3 influence
//   const radius = TILE_SIZE * 1.35;
//
//   ctx.beginPath();
//   ctx.arc(px, py, radius, 0, Math.PI * 2);
//
//   // fill NEVER changes due to remote busy
//   ctx.fillStyle = bear.locked ? "#1e293b" : "#0a1f44";
//   ctx.fill();
//
//   // stroke ONLY shows busy
//   if (isRemoteBusy) {
//     ctx.strokeStyle = "#dc2626";
//     ctx.lineWidth = 3;
//     ctx.stroke();
//   }
//
//   /* ===============================
//      Bear label
//   =============================== */
//   ctx.save();
//   ctx.translate(px, py);
//   ctx.rotate(-Math.PI / 4);
//   ctx.fillStyle = "#ffffff";
//   ctx.font = `bold ${Math.max(12, TILE_SIZE * 0.35)}px sans-serif`;
//   ctx.textAlign = "center";
//   ctx.textBaseline = "middle";
//   ctx.fillText(String(bear.id ?? ""), 0, 0);
//   ctx.restore();
//
//   /* ===============================
//      IN USE label (centred)
//   =============================== */
// /* ===============================
//    IN USE label (centred on circle)
// =============================== */
// if (isRemoteBusy) {
//   ctx.save();
//
//   // 1. Move to exact circle centre
//   ctx.translate(px, py);
//
//   // 2. Rotate once
//   ctx.rotate(-Math.PI / 4);
//
//   // 3. Move UP after rotation (pure Y axis)
//   ctx.translate(0, -radius + 10);
//
//   ctx.fillStyle = "#dc2626";
//   ctx.font = "bold 11px sans-serif";
//   ctx.textAlign = "center";
//   ctx.textBaseline = "middle";
//
//   ctx.fillText("IN USE", 0, 20);
//
//   ctx.restore();
// }
//
//
// // -------- Locked indicator --------
// if (bear.locked) {
//   ctx.save();
//
//   // anchor exactly at bear centre
//   ctx.translate(px, py);
//
//   // same rotation as labels
//   ctx.rotate(-Math.PI / 4);
//
//   ctx.font = "14px sans-serif";
//   ctx.textAlign = "center";
//   ctx.textBaseline = "middle";
//   ctx.fillStyle = "#ffffff";
//
//   // draw lock slightly below centre (Y only)
//   ctx.fillText("🔒", 0, TILE_SIZE * 0.45);
//
//   ctx.restore();
// }
//
// }
//
// function drawCastle(castle) {
//     if (!castle || castle.x == null || castle.y == null) return;
//
//     const px = castle.x * TILE_SIZE;
//     const py = castle.y * TILE_SIZE;
//     const size = TILE_SIZE * 2;
//
//     const isRemoteBusy =
//         window.remoteBusy?.has(castle.id) &&
//         draggingCastle?.id !== castle.id;
//
//
//     // -------- body --------
//     // ctx.fillStyle = castle.locked
//     //     ? "#374151"
//     //     : efficiencyColor(castle.efficiency ?? 99);
//
//     ctx.fillStyle = efficiencyColor(castle.efficiency ?? 99);
//
//     ctx.fillRect(px + 2, py + 2, size - 4, size - 4);
//
//     // -------- border --------
//     ctx.save();
//     ctx.strokeStyle = isRemoteBusy ? "#dc2626" : "#e5e7eb";
//     ctx.lineWidth = isRemoteBusy ? 3 : 1;
//
//     ctx.strokeRect(px + 2, py + 2, size - 4, size - 4);
//     ctx.restore();
//
//     // -------- text --------
//     ctx.save();
//     ctx.translate(px + size / 2, py + size / 2);
//     ctx.rotate(-Math.PI / 4);
//
//     ctx.fillStyle = "white";
//     ctx.textAlign = "center";
//
//     ctx.font = "bold 10px sans-serif";
//     ctx.fillText(String(castle.player ?? ""), 0, -6);
//
//     ctx.font = "12px sans-serif";
//     ctx.fillText(`Lv ${castle.player_level ?? "-"}`, 0, 10);
//
//     ctx.font = "11px sans-serif";
//     ctx.fillText(`Pref: ${castle.preference ?? ""}`, 0, 24);
//
//     if (isRemoteBusy) {
//         ctx.fillStyle = "#d90000";
//         ctx.font = "bold 11px sans-serif";
//         ctx.fillText("IN USE", 0, -20);
//     }
//     ctx.restore();
//
//     // -------- lock icon --------
//     if (castle.locked) {
//         ctx.save();
//         ctx.translate(px + size / 2, py + size + 8);
//         ctx.rotate(-Math.PI / 4);
//         ctx.font = "12px sans-serif";
//         ctx.textAlign = "center";
//         ctx.fillStyle = "white";
//         ctx.fillText("🔒", 35, 5);
//         ctx.restore();
//     }
//
//
// }
//
// function efficiencyColor(value) {
//     if (value == null) return "#374151";
//     if (!mapData?.efficiency_scale) return "#374151";
//
//     for (const tier of mapData.efficiency_scale) {
//         if (value <= tier.max) {
//             return tier.color;
//         }
//     }
//
//     return mapData.efficiency_scale.at(-1).color;
// }
//
// function renderEfficiencyLegend() {
//     const container = document.getElementById("efficiencyLegend");
//     if (!container || !mapData?.efficiency_scale) return;
//
//     container.innerHTML = "";
//
//     mapData.efficiency_scale.forEach(tier => {
//         const row = document.createElement("div");
//         row.className = "legend-row";
//
//         const swatch = document.createElement("span");
//         swatch.className = "legend-swatch";
//         swatch.style.background = tier.color;
//
//         const label = document.createElement("span");
//         label.textContent = tier.label;
//
//         row.appendChild(swatch);
//         row.appendChild(label);
//         container.appendChild(row);
//     });
// }
//
// renderEfficiencyLegend();
//
// function onMouseDown(e) {
//   if (!mapData) return;
//   if (draggingCastle || draggingBear) return;
//
//   const rect = canvas.getBoundingClientRect();
//   const { x, y } = screenToGrid(
//     e.clientX - rect.left,
//     e.clientY - rect.top
//   );
//
//   // ---- CASTLES FIRST ----
//   for (let castle of mapData.castles || []) {
//     if (castle.x == null || castle.y == null) continue;
//
//     if (isPointInCastle(x, y, castle)) {
//       if (castle.locked) return;
//       if (window.remoteBusy?.has(castle.id)) return;
//
//       draggingCastle = castle;
//       Sync.markBusy(castle.id);
//
//       castle._original = { x: castle.x, y: castle.y };
//       castle._grab = { dx: x - castle.x, dy: y - castle.y };
//
//       drawMap(mapData);
//       return;
//     }
//   }
//
//   // ---- THEN BEARS ----
//   for (let bear of mapData.bear_traps || []) {
//     if (
//       x >= bear.x - 1 && x <= bear.x + 1 &&
//       y >= bear.y - 1 && y <= bear.y + 1
//     ) {
//       if (bear.locked) return;
//       if (window.remoteBusy?.has(bear.id)) return;
//
//       draggingBear = bear;
//       Sync.markBusy(bear.id);
//
//       bear._original = { x: bear.x, y: bear.y };
//
//       drawMap(mapData);
//       return;
//     }
//   }
// }
//
// function onMouseMove(e) {
//     if (!mapData) return;
//     if (!draggingCastle && !draggingBear) return;
//
//     const rect = canvas.getBoundingClientRect();
//     const {x, y} = screenToGrid(
//         e.clientX - rect.left,
//         e.clientY - rect.top
//     );
//
//     // ---- CASTLE DRAG ----
//     if (draggingCastle) {
//         if (!draggingCastle._grab) return;
//
//         const nx = x - draggingCastle._grab.dx;
//         const ny = y - draggingCastle._grab.dy;
//
//         // clamp to grid bounds (soft clamp)
//         draggingCastle.x = Math.max(
//             0,
//             Math.min(mapData.grid_size - 2, nx)
//         );
//         draggingCastle.y = Math.max(
//             0,
//             Math.min(mapData.grid_size - 2, ny)
//         );
//
//         drawMap(mapData);
//         return;
//     }
//
//     // ---- BEAR DRAG ----
//     if (draggingBear) {
//         draggingBear.x = Math.max(
//             0,
//             Math.min(mapData.grid_size - 1, x)
//         );
//         draggingBear.y = Math.max(
//             0,
//             Math.min(mapData.grid_size - 1, y)
//         );
//
//         drawMap(mapData);
//     }
// }
//
// function onMouseUp() {
//   if (!draggingCastle) return;
//
//   const c = draggingCastle;
//   draggingCastle = null;
//
//   // snap to integers ONLY for visuals
//   const x = Math.round(c.x);
//   const y = Math.round(c.y);
//
//   fetch("/api/intent/move_castle", {
//     method: "POST",
//     headers: { "Content-Type": "application/json" },
//     body: JSON.stringify({ id: c.id, x, y })
//   });
//
//   Sync.unmarkBusy(c.id);
// }
//
// function onCanvasContextMenu(e) {
//   e.preventDefault();
//   if (!mapData) return;
//
//   const rect = canvas.getBoundingClientRect();
//   const { x, y } = screenToGrid(
//     e.clientX - rect.left,
//     e.clientY - rect.top
//   );
//
//   // ---- CASTLES FIRST ----
//   for (let castle of mapData.castles || []) {
//     if (isPointInCastle(x, y, castle)) {
//       castle.locked = !castle.locked;
//
//       drawMap(mapData);
//       renderCastleTable();
//
//       Sync.scheduleUpdate({
//         id: castle.id,
//         locked: castle.locked
//       });
//
//       autosaveCastle(castle, ["locked"]);
//       return;
//     }
//   }
//
//   // ---- THEN BEARS ----
//   for (let bear of mapData.bear_traps || []) {
//     if (
//       x >= bear.x - 1 && x <= bear.x + 1 &&
//       y >= bear.y - 1 && y <= bear.y + 1
//     ) {
//       bear.locked = !bear.locked;
//
//       drawMap(mapData);
//
//       Sync.scheduleUpdate({
//         id: bear.id,
//         locked: bear.locked
//       });
// autosaveBear(bear, ["locked"]);
//       return;
//     }
//   }
// }
//
// // ==========================
// // Event Listeners
// // ==========================
// function toggleCastleLock(castle) {
//   if (!castle) return;
//
//   castle.locked = !castle.locked;
//
//   drawMap(mapData);
//   renderCastleTable();
//
//   if (window.Sync?.scheduleUpdate) {
//     Sync.scheduleUpdate({
//       id: castle.id,
//       locked: castle.locked
//     });
//   }
//
//   autosaveCastle(castle, ["locked"]);
// }
// function toggleBearLock(bear) {
//   if (!bear) return;
//
//   bear.locked = !bear.locked;
//
//   drawMap(mapData);
//
//   if (window.Sync?.scheduleUpdate) {
//     Sync.scheduleUpdate({
//       id: bear.id,
//       locked: bear.locked
//     });
//   }
// }
//
// canvas.addEventListener("mousedown", onMouseDown);
// canvas.addEventListener("mousemove", onMouseMove);
// canvas.addEventListener("mouseup", onMouseUp);
// canvas.addEventListener("mouseleave", onMouseUp);
// canvas.addEventListener("contextmenu", onCanvasContextMenu);
//
// //
// // document
// //     .getElementById("downloadBtn")
// //     .addEventListener("click", downloadMapImage);
// //
// // document.getElementById("autoPlaceBtn")
// //     ?.addEventListener("click", autoPlaceCastles);
// //
// // document
// //     .getElementById("uploadCsvBtn")
// //     .addEventListener("click", () => {
// //         document.getElementById("csvUpload").click();
// //     });
//
// document
//     .getElementById("csvUpload")
//     .addEventListener("change", e => {
//         const file = e.target.files[0];
//         if (!file) return;
//
//         const reader = new FileReader();
//
//         reader.onload = () => {
//             try {
//                 const csvText = reader.result;
//
//                 //Parse CSV → castles
//                 const csvCastles = castlesFromCSV(csvText);
//
//                 //Merge into CURRENT map state
//                 mapData.castles = mergeCastles(
//                     mapData.castles || [],
//                     csvCastles
//                 );
//
//                 //Compute dynamic priorities
//                 fetch("/api/recompute/priorities", { method: "POST" });
//
//                 //Redraw
//                 drawMap(mapData);
//
//                 // reset input
//                 e.target.value = "";
//
//                 console.log("CSV merged:", mapData.castles.length);
//             } catch (err) {
//                 console.error(err);
//                 alert("Failed to load CSV");
//             }
//         };
//
//         reader.readAsText(file);
//     });
//
// // ==========================
// // Sync → App hooks
// // ==========================
// window.applyRemoteUpdate = function (update) {
//   if (!mapData || !update?.id) return;
//
//   // 1️⃣ Try castles first
//   let entity = mapData.castles?.find(c => c.id === update.id);
//
//   // 2️⃣ Then bears
//   if (!entity) {
//     entity = mapData.bear_traps?.find(b => b.id === update.id);
//   }
//
//   // 3️⃣ Unknown entity → ignore safely
//   if (!entity) return;
//
//   // 4️⃣ Apply update
//   Object.assign(entity, update);
//
//   // 5️⃣ Recompute dependent values if needed
//   if ("x" in update || "y" in update) {
//     mapData.castles.forEach(c => {
//       c.efficiency = calculateEfficiency(c, mapData.bear_traps);
//     });
//   }
//
//   // 6️⃣ Redraw
//   drawMap(mapData);
//   renderCastleTable?.();
// };
//
//
// function applyStateToEntities(localList, remoteMap) {
//   if (!localList || !remoteMap) return;
//
//   localList.forEach(entity => {
//     const remote = remoteMap[entity.id];
//     if (remote) {
//       Object.assign(entity, remote);
//     }
//   });
// }
//
//
// window.loadFullState = function (state) {
//   if (!mapData || !state) return;
//
//   // ---- CASTLES ----
//   if (state.castles) {
//     mapData.castles.forEach(c => {
//       const remote = state.castles[c.id];
//       if (remote) Object.assign(c, remote);
//     });
//   }
//
//   // ---- BEARS ----
//   if (state.bears) {
//     mapData.bear_traps.forEach(b => {
//       const remote = state.bears[b.id];
//       if (remote) Object.assign(b, remote);
//     });
//   }
//
//   drawMap(mapData);
//   renderCastleTable?.();
// };
//
// const searchInput = document.getElementById("castleSearch");
//
// if (searchInput) {
//   searchInput.addEventListener("input", () => {
//     renderCastleTable();
//   });
// }
//
// document.getElementById("howToBtn").addEventListener("click", () => {
//   alert(`
// BEAR PLANNER — HOW TO USE
//
// PLACEMENT
// • Drag castles to reposition them on the grid
// • Castles snap to valid tiles only
// • Auto Place respects player preferences
//
// LOCKING
// • Right-click a CASTLE to lock or unlock it
// • Locked castles cannot be moved or auto-placed
// • Right-click a BEAR to lock or unlock its position
// • If something won’t move — it is locked
//
// AUTO PLACE
// • Places strongest + committed players closest to their bear
// • Players marked “both” are placed along the spine
// • Existing locks are never overridden
//
// EFFICIENCY
// • Lower efficiency values are better
// • Colours indicate placement quality (not errors)
// • Red is reserved for server or hard lock states
//
// TABLE
// • Use search to filter instantly
// • Lock All applies to already placed castles
// • Unlock All clears manual locks
//
// TIP
// • Always lock bears before running Auto Place
// • Lock priority players manually if required
// `);
// });
//
//
//
document
  .getElementById("castleTable")
  .addEventListener("click", e => {
    const th = e.target.closest("th[data-sort]");
    if (!th) return;
    sortCastles(th.dataset.sort);
  });

// window.Sync = Sync;
