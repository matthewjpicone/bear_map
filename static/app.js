// ==========================
// State variables
// ==========================
let draggingBear = null;        // mouse interaction only
let draggingCastle = null;     // mouse interaction only
let draggingBanner = null;
let mapData = null;            // hydrated from server, mutated locally for UI
let castleSort = {             // table UI concern
  key: null,
  asc: true
};
// Viewport state
let viewZoom = 1;     // Zoom level (1 = 100%)
let viewOffsetX = 0;  // Pan offset X
let viewOffsetY = 0;  // Pan offset Y
let isPanning = false;
let lastPanX = 0;
let lastPanY = 0;
const MIN_ZOOM = 0.1;
const MAX_ZOOM = 3;
window.remoteBusy = new Set(); // sync / optimistic UI guard

// Grid visibility state
let showGrid = true;

// Tooltip state
let hoveredCastleOnCanvas = null;

// ==========================
// Animation state
// ==========================
const ANIMATION_DURATION = 300; // ms
const animationState = new Map(); // Map<entityId, {fromX, fromY, toX, toY, startTime}>
let animationFrameId = null;

// ==========================
// Bulk operations state
// ==========================
let selectedCastleIds = new Set();

// ==========================
// Table filtering state
// ==========================
let visibleCastleIds = new Set();
let hoveredCastleId = null;

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

    // Single message handler for all events
    sse.onmessage = async evt => {
      try {
        const msg = JSON.parse(evt.data);
        console.log("[SSE] message:", evt.data);  // Log all messages

        if (msg.type === "config_update") {
          // Authoritative signal: server says map data changed
          const ok = await loadMapData();
          if (!ok) return;

          renderCastleTable();
          drawMap(mapData);
        }
        // Add more type checks here if needed
      } catch (error) {
        console.error("[SSE] Error parsing message:", error);
      }
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

  // Center the rotated grid
  viewOffsetX = 0;
  viewOffsetY = (mapData.grid_size * TILE_SIZE) * (Math.SQRT2 / 2);

  renderCastleTable();
  drawMap(mapData);

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
    locked: !!bear.locked,
    size: { w: 3, h: 3, ox: 1, oy: 1 }  // 3x3 centered on (x,y)
  };
}

function normaliseCastle(castle, index) {
  return {
    id: castle.id ?? `Castle ${index + 1}`,
    player: (castle.player ?? "").substring(0, 20),  // Limit to 20 chars
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
    round_trip: castle.round_trip ? Number(castle.round_trip) : "NA",

    last_updated: castle.last_updated ? new Date(castle.last_updated) : null,  // New field

    x: typeof castle.x === "number" ? castle.x : null,
    y: typeof castle.y === "number" ? castle.y : null,

    locked: !!castle.locked,
    size: { w: 2, h: 2, ox: 0, oy: 0 }  // 2x2 square from (x,y)
  };
}

function normaliseBanner(banner, index) {
  return {
    id: banner.id ?? `B${index + 1}`,
    x: typeof banner.x === "number" ? banner.x : null,
    y: typeof banner.y === "number" ? banner.y : null,
    locked: !!banner.locked,
    size: { w: 1, h: 1, ox: 0, oy: 0 }  // 1x1 square from (x,y)
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
// Tooltip Functions
// ==========================
function showCastleTooltip(castle, mouseX, mouseY) {
  const tooltip = document.getElementById("castleTooltip");
  if (!tooltip || !castle) return;

  // Format the tooltip content
  const lastUpdated = castle.last_updated 
    ? castle.last_updated.toLocaleString() 
    : "Never";

  tooltip.innerHTML = `
    <div class="tooltip-title">${castle.player || "Unknown"}</div>
    <div class="tooltip-row">
      <span class="tooltip-label">Power:</span>
      <span class="tooltip-value">${castle.power?.toLocaleString() || 0}</span>
    </div>
    <div class="tooltip-row">
      <span class="tooltip-label">Player Level:</span>
      <span class="tooltip-value">${castle.player_level || 0}</span>
    </div>
    <div class="tooltip-row">
      <span class="tooltip-label">Command Centre:</span>
      <span class="tooltip-value">${castle.command_centre_level || 0}</span>
    </div>
    <div class="tooltip-row">
      <span class="tooltip-label">Attendance:</span>
      <span class="tooltip-value">${castle.attendance ?? "—"}</span>
    </div>
    <div class="tooltip-row">
      <span class="tooltip-label">Preference:</span>
      <span class="tooltip-value">${castle.preference || "—"}</span>
    </div>
    <div class="tooltip-row">
      <span class="tooltip-label">Priority:</span>
      <span class="tooltip-value">${castle.priority ?? "—"}</span>
    </div>
    <div class="tooltip-row">
      <span class="tooltip-label">Efficiency:</span>
      <span class="tooltip-value">${castle.efficiency ?? "—"}</span>
    </div>
    <div class="tooltip-row">
      <span class="tooltip-label">Last Updated:</span>
      <span class="tooltip-value">${lastUpdated}</span>
    </div>
    <div class="tooltip-row">
      <span class="tooltip-label">Locked:</span>
      <span class="tooltip-value">${castle.locked ? "Yes 🔒" : "No"}</span>
    </div>
  `;

  // Position the tooltip over the castle
  tooltip.style.display = "block";
  
  // If castle has grid coordinates, position tooltip over the castle
  if (castle.x != null && castle.y != null) {
    const screenPos = gridToScreen(castle.x, castle.y);
    tooltip.style.left = `${screenPos.x}px`;
    tooltip.style.top = `${screenPos.y}px`;
  } else {
    // Fallback to mouse position for castles not on the map
    tooltip.style.left = `${mouseX + 15}px`;
    tooltip.style.top = `${mouseY + 15}px`;
  }

  // Adjust position if tooltip goes off-screen
  const rect = tooltip.getBoundingClientRect();
  const offsetX = 10;
  const offsetY = 10;
  
  // Check if tooltip goes off right edge
  if (rect.right > window.innerWidth) {
    tooltip.style.left = `${window.innerWidth - rect.width - offsetX}px`;
  }
  // Check if tooltip goes off bottom edge
  if (rect.bottom > window.innerHeight) {
    tooltip.style.top = `${window.innerHeight - rect.height - offsetY}px`;
  }
  // Check if tooltip goes off left edge
  if (rect.left < 0) {
    tooltip.style.left = `${offsetX}px`;
  }
  // Check if tooltip goes off top edge
  if (rect.top < 0) {
    tooltip.style.top = `${offsetY}px`;
  }
  
  // Trigger animation after positioning
  setTimeout(() => tooltip.classList.add("visible"), 10);
}

function hideCastleTooltip() {
  const tooltip = document.getElementById("castleTooltip");
  if (tooltip) {
    tooltip.classList.remove("visible");
    // Hide after animation completes
    setTimeout(() => {
      tooltip.style.display = "none";
    }, 150);
  }
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

function tdDelete(c) {
  const td = document.createElement("td");
  const btn = document.createElement("button");
  btn.classList.add("delete-btn");
  btn.innerHTML = "🗑️";
  btn.onclick = () => {
    const modal = document.getElementById("deleteModal");
    document.getElementById("deleteTitle").textContent = `Delete Player ${c.player}`;
    modal.dataset.castleId = c.id;  // Store ID
    modal.style.display = "block";
    document.getElementById("deleteReason").value = "";
    document.getElementById("deleteOther").style.display = "none";
    document.getElementById("deleteOther").value = "";
    // Trigger animation after display
    setTimeout(() => modal.classList.add("visible"), 10);
  };
  td.appendChild(btn);
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
// Unified Entity Hit Detection
// ==========================
function isPointInEntity(gx, gy, entity) {
  const size = entity.size;
  return (
    gx >= entity.x - size.ox &&
    gx < entity.x - size.ox + size.w &&
    gy >= entity.y - size.oy &&
    gy < entity.y - size.oy + size.h
  );
}

// ==========================
// Table Rendering
// ==========================

// function renderCastleTable() {
//   const tbody = document.getElementById("castleTableBody");
//   const query = document.getElementById("castleSearch")?.value
//     .trim()
//     .toLowerCase();
//
//   // Always use the latest mapData.castles (updated by SSE)
//   let castles = [...mapData.castles];  // Shallow copy to avoid modifying original
//
//   // Apply current sort to the copy
//   if (castleSort.key) {
//     castles.sort((a, b) => {
//       let va = a[castleSort.key];
//       let vb = b[castleSort.key];
//
//       if (va == null && vb == null) return 0;
//       if (va == null) return 1;
//       if (vb == null) return -1;
//
//       if (va instanceof Date && vb instanceof Date) return (va.getTime() - vb.getTime()) * (castleSort.asc ? 1 : -1);  // Handle dates
//       if (typeof va === "boolean") return (va === vb ? 0 : va ? 1 : -1) * (castleSort.asc ? 1 : -1);
//       if (typeof va === "number") return (va - vb) * (castleSort.asc ? 1 : -1);
//       return va.toString().localeCompare(vb.toString()) * (castleSort.asc ? 1 : -1);
//     });
//   }
//
//   // Apply filter to the (possibly sorted) copy
//   if (query) {
//     castles = castles.filter(c => {
//       const haystack = [c.id, c.player, c.preference].join(" ").toLowerCase();
//       return haystack.includes(query);
//     });
//   }
//
//   tbody.innerHTML = "";
//
//   castles.forEach(c => {
//     const tr = document.createElement("tr");
//
//     /* ID */
//     const idTd = document.createElement("td");
//     idTd.appendChild(highlightText(c.id, query));
//     tr.appendChild(idTd);
//
//     /* Player */
//     const playerTd = tdInput("player", c);
//     if (query && c.player?.toLowerCase().includes(query)) {
//       playerTd.querySelector("input")?.classList.add("match-input");
//     }
//     tr.appendChild(playerTd);
//
//     tr.appendChild(tdNumber("power", c));
//     tr.appendChild(tdNumber("player_level", c));
//     tr.appendChild(tdNumber("command_centre_level", c));
//     tr.appendChild(tdNumber("attendance", c));
//     tr.appendChild(tdSelect("preference", c, ["Bear 1", "Bear 2", "Both"]));
//     tr.appendChild(tdCheckbox("locked", c));
//     tr.appendChild(tdReadonly(c.rallies_30min));  // Read-only Rallies/Session
//     tr.appendChild(tdReadonly(c.round_trip || "NA"));  // New read-only Round Trip Time (s)
//     tr.appendChild(tdReadonly(c.priority));
//     tr.appendChild(tdReadonly(c.efficiency));
//     tr.appendChild(tdReadonly(c.last_updated ? c.last_updated.toLocaleString() : "Never"));  // Last Updated
// tr.appendChild(tdDelete(c));
//     tbody.appendChild(tr);
//   });
//
//   enableTableSorting();
//   updateSortIndicators();
// }

function renderCastleTable() {
  const tbody = document.getElementById("castleTableBody");
  const query = document.getElementById("castleSearch")?.value
    .trim()
    .toLowerCase();

  // Always use the latest mapData.castles (updated by SSE)
  let castles = [...mapData.castles];  // Shallow copy

  // Apply limit based on priority (top N highest priority)
  const limit = document.getElementById("castleLimit").value;
  if (limit !== "all") {
    castles.sort((a, b) => (b.priority || 0) - (a.priority || 0));  // Highest priority first
    castles = castles.slice(0, parseInt(limit));
  }

  // Apply search filter to the (possibly limited) castles
  if (query) {
    castles = castles.filter(c => {
      const haystack = [c.id, c.player, c.preference].join(" ").toLowerCase();
      return haystack.includes(query);
    });
  }

  // Apply current sort to the (possibly limited and searched) castles
  if (castleSort.key) {
    castles.sort((a, b) => {
      let va = a[castleSort.key];
      let vb = b[castleSort.key];

      if (va == null && vb == null) return 0;
      if (va == null) return 1;
      if (vb == null) return -1;

      if (va instanceof Date && vb instanceof Date) return (va.getTime() - vb.getTime()) * (castleSort.asc ? 1 : -1);
      if (typeof va === "boolean") return (va === vb ? 0 : va ? 1 : -1) * (castleSort.asc ? 1 : -1);
      if (typeof va === "number") return (va - vb) * (castleSort.asc ? 1 : -1);
      return va.toString().localeCompare(vb.toString()) * (castleSort.asc ? 1 : -1);
    });
  }

  // Check if filters are active (for fading)
  const limitActive = limit !== "all";
  const searchActive = query.length > 0;
  const filterActive = limitActive || searchActive;

  if (filterActive) {
    visibleCastleIds = new Set(castles.map(c => c.id));
  } else {
    visibleCastleIds = new Set();
  }

  // Redraw map to apply fading/highlights
  drawMap(mapData);

  tbody.innerHTML = "";

  castles.forEach(c => {
    const tr = document.createElement("tr");
    tr.dataset.castleId = c.id; // Track castle ID for animations
    tr.classList.add("fade-in"); // Add fade-in animation for new rows

    tr.addEventListener("mouseenter", (e) => {
      hoveredCastleId = c.id;
      drawMap(mapData);
      showCastleTooltip(c, e.clientX, e.clientY);
    });
    tr.addEventListener("mouseleave", () => {
      hoveredCastleId = null;
      drawMap(mapData);
      hideCastleTooltip();
    });
    tr.addEventListener("mousemove", (e) => {
      // Update tooltip position as mouse moves over table row
      if (hoveredCastleId === c.id) {
        showCastleTooltip(c, e.clientX, e.clientY);
      }
    });
tr.addEventListener("click", (e) => {
  // Don't pan if clicking on checkbox or input elements
  if (e.target.type === 'checkbox' || e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT' || e.target.tagName === 'BUTTON') {
    return;
  }
  
  // Pan to center of castle in rotated view
  const castleCenterX = c.x * TILE_SIZE + TILE_SIZE;
  const castleCenterY = c.y * TILE_SIZE + TILE_SIZE;
  const rad = (ISO_DEG * Math.PI) / 180;
  const cos = Math.cos(rad);
  const sin = Math.sin(rad);
  const rx = castleCenterX * cos - castleCenterY * sin;
  const ry = castleCenterX * sin + castleCenterY * cos;
  viewOffsetX = rx;
  viewOffsetY = ry;
  drawMap(mapData);
});

    /* Checkbox for bulk selection */
    const checkboxTd = document.createElement("td");
    checkboxTd.classList.add("checkbox-col");
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.dataset.castleId = c.id;
    checkbox.checked = selectedCastleIds.has(c.id);
    checkbox.addEventListener('change', (e) => {
      e.stopPropagation();
      toggleCastleSelection(c.id, checkbox.checked);
    });
    checkboxTd.appendChild(checkbox);
    tr.appendChild(checkboxTd);

    /* ID */
    const idTd = document.createElement("td");
    idTd.appendChild(highlightText(c.id, query));
    tr.appendChild(idTd);

    /* Player */
    const playerTd = tdInput("player", c);
    if (query && c.player?.toLowerCase().includes(query)) {
      playerTd.querySelector("input")?.classList.add("match-input");
    }
    tr.appendChild(playerTd);

    tr.appendChild(tdNumber("power", c));
    tr.appendChild(tdNumber("player_level", c));
    tr.appendChild(tdNumber("command_centre_level", c));
    tr.appendChild(tdNumber("attendance", c));
    tr.appendChild(tdSelect("preference", c, ["Bear 1", "Bear 2", "Both"]));
    tr.appendChild(tdCheckbox("locked", c));
    tr.appendChild(tdReadonly(c.rallies_30min));  // Read-only Rallies/Session
    tr.appendChild(tdReadonly(c.round_trip || "NA"));  // New read-only Round Trip Time (s)
    tr.appendChild(tdReadonly(c.priority));
    tr.appendChild(tdReadonly(c.efficiency));
    tr.appendChild(tdReadonly(c.last_updated ? c.last_updated.toLocaleString() : "Never"));  // Last Updated
    tr.appendChild(tdDelete(c));  // Delete

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
    .querySelectorAll("#castleTable th[data-sort]")
    .forEach(th => {
      th.style.cursor = "pointer";
      th.onclick = () => {
        console.log("Sorting by:", th.dataset.sort);  // Debug log
        sortCastles(th.dataset.sort);
      };
    });
}

// Enable table sorting functionality and apply initial sort indicators
enableTableSorting();
updateSortIndicators();

// ==========================
// Render and Placement
// ==========================
const ISO_DEG = 45;

function clamp(v, min, max) {
  return Math.max(min, Math.min(max, v));
}

function getViewMatrix() {
  const centerX = canvas.width / 2;
  const centerY = canvas.height / 2;

  // Same order as drawMap:
  // translate(center) -> scale(zoom) -> translate(-offset) -> rotate(45deg)
  return new DOMMatrix()
    .translateSelf(centerX, centerY)
    .scaleSelf(viewZoom, viewZoom)
    .translateSelf(-viewOffsetX, -viewOffsetY)
    .rotateSelf(ISO_DEG);
}

function screenToGrid(mouseX, mouseY) {
  if (!mapData) return { x: 0, y: 0 };

  const size = mapData.grid_size;
  const inv = getViewMatrix().inverse();
  const p = new DOMPoint(mouseX, mouseY).matrixTransform(inv);

  const gridX = Math.floor(p.x / TILE_SIZE);
  const gridY = Math.floor(p.y / TILE_SIZE);

  return {
    x: clamp(gridX, 0, size - 1),
    y: clamp(gridY, 0, size - 1)
  };
}

function gridToScreen(gridX, gridY) {
  if (!mapData) return { x: 0, y: 0 };

  const rect = canvas.getBoundingClientRect();
  // Convert grid coordinates to pixel coordinates on the canvas
  const px = (gridX + 0.5) * TILE_SIZE; // Center of the tile
  const py = (gridY + 0.5) * TILE_SIZE; // Center of the tile
  
  // Apply the view matrix transformation
  const p = new DOMPoint(px, py).matrixTransform(getViewMatrix());
  
  return {
    x: p.x + rect.left,
    y: p.y + rect.top
  };
}

// ==========================
// Animation helpers
// ==========================
function startAnimation(entityId, fromX, fromY, toX, toY) {
  if (fromX === toX && fromY === toY) return; // No movement needed
  
  animationState.set(entityId, {
    fromX,
    fromY,
    toX,
    toY,
    startTime: performance.now()
  });
  
  if (!animationFrameId) {
    animationFrameId = requestAnimationFrame(animationLoop);
  }
}

function animationLoop(currentTime) {
  let hasActiveAnimations = false;
  
  for (const [entityId, anim] of animationState.entries()) {
    const elapsed = currentTime - anim.startTime;
    const progress = Math.min(elapsed / ANIMATION_DURATION, 1);
    
    if (progress >= 1) {
      animationState.delete(entityId);
    } else {
      hasActiveAnimations = true;
    }
  }
  
  // Redraw with interpolated positions
  drawMap(mapData);
  
  if (hasActiveAnimations) {
    animationFrameId = requestAnimationFrame(animationLoop);
  } else {
    animationFrameId = null;
  }
}

function getAnimatedPosition(entity) {
  if (!entity || entity.x == null || entity.y == null) {
    return { x: entity?.x, y: entity?.y };
  }
  
  const anim = animationState.get(entity.id);
  if (!anim) {
    return { x: entity.x, y: entity.y };
  }
  
  const elapsed = performance.now() - anim.startTime;
  const progress = Math.min(elapsed / ANIMATION_DURATION, 1);
  
  // Ease-out cubic for smooth deceleration
  const eased = 1 - Math.pow(1 - progress, 3);
  
  return {
    x: anim.fromX + (anim.toX - anim.fromX) * eased,
    y: anim.fromY + (anim.toY - anim.fromY) * eased
  };
}

function drawMap(data) {
  if (!data || !canvas || !ctx) return;

  const size = data.grid_size ?? 0;
  if (size <= 0) return;

  const container = canvas.parentElement;
  canvas.width = container.clientWidth;
  canvas.height = container.clientHeight;

  ctx.clearRect(0, 0, canvas.width, canvas.height);

  ctx.save();

  // Apply the shared matrix
  ctx.setTransform(getViewMatrix());

  // Grid (conditionally rendered based on showGrid state)
  if (showGrid) {
    ctx.strokeStyle = "#ccc";
    ctx.lineWidth = 1 / viewZoom;
    for (let x = 0; x < size; x++) {
      for (let y = 0; y < size; y++) {
        ctx.strokeRect(x * TILE_SIZE, y * TILE_SIZE, TILE_SIZE, TILE_SIZE);
      }
    }
  }

  data.banners.forEach(drawBanner);
  data.bear_traps.forEach(drawBearTrap);
  data.castles.forEach(drawCastle);

  ctx.restore();
  renderEfficiencyLegend();
}


function drawBanner(banner) {
  if (!banner || banner.x == null || banner.y == null || !mapData) return;

  const gridSize = mapData.grid_size;
  // Use animated position if available
  const pos = getAnimatedPosition(banner);
  const px = pos.x * TILE_SIZE;
  const py = pos.y * TILE_SIZE;
  const cx = Math.round(pos.x);
  const cy = Math.round(pos.y);

  const isRemoteBusy =
    window.remoteBusy?.has(banner.id) &&
    draggingBanner?.id !== banner.id;

  // -------- Influence area (7x7, light green fill only) --------
  // Only show when any banner is being moved (global overlay for all banners)
  if (draggingBanner) {
    ctx.fillStyle = "rgba(34, 197, 94, 0.35)";  // Light green fill
    for (let x = cx - 3; x <= cx + 3; x++) {
      for (let y = cy - 3; y <= cy + 3; y++) {
        if (x < 0 || y < 0 || x >= gridSize || y >= gridSize) continue;
        const tilePx = x * TILE_SIZE;
        const tilePy = y * TILE_SIZE;
        ctx.fillRect(tilePx, tilePy, TILE_SIZE, TILE_SIZE);
      }
    }
  }

  // -------- Banner rectangle --------
  ctx.fillStyle = "#1e3a8a";
  ctx.fillRect(px, py, TILE_SIZE, TILE_SIZE);

  ctx.strokeStyle = "#ffffff";
  ctx.lineWidth = 1 / viewZoom;  // Scale line width
  ctx.strokeRect(px, py, TILE_SIZE, TILE_SIZE);

  // -------- Banner label --------
  ctx.save();
  ctx.translate(px + TILE_SIZE / 2, py + TILE_SIZE / 2);
  ctx.rotate(-Math.PI / 4);

  const scale = Math.min(1 + (viewZoom - 1) * 0.1, 1.2);  // Smoother, smaller max scaling
  ctx.fillStyle = "#ffffff";
  ctx.font = `bold ${Math.max(12, TILE_SIZE * 0.35) * scale}px sans-serif`;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";

  ctx.fillText(String(banner.id ?? ""), 0, 0);
  ctx.restore();

  // -------- IN USE label --------
  if (isRemoteBusy) {
    ctx.save();
    ctx.translate(px + TILE_SIZE / 2, py + TILE_SIZE / 2);
    ctx.rotate(-Math.PI / 4);
    ctx.translate(0, -TILE_SIZE / 2 + 10);  // Position above center

    ctx.fillStyle = "#dc2626";
    ctx.font = `bold ${11 * scale}px sans-serif`;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";

    ctx.fillText("IN USE", 0, 0);
    ctx.restore();
  }

  // -------- Locked indicator --------
  if (banner.locked) {
    ctx.save();
    ctx.translate(px + TILE_SIZE / 2, py + TILE_SIZE / 2);
    ctx.rotate(-Math.PI / 4);

    ctx.fillStyle = "#ffffff";
    ctx.font = `${14 * scale}px sans-serif`;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";

    ctx.fillText("🔒", 0, TILE_SIZE * 0.45);  // Below center
    ctx.restore();
  }
}

function drawBearTrap(bear) {
  if (!bear || bear.x == null || bear.y == null || !mapData) return;

  const gridSize = mapData.grid_size;
  // Use animated position if available
  const pos = getAnimatedPosition(bear);
  const cx = Math.round(pos.x);
  const cy = Math.round(pos.y);

  const isRemoteBusy =
    window.remoteBusy?.has(bear.id) &&
    draggingBear?.id !== bear.id;

  /* ===============================
     Influence tiles (3x3)
  =============================== */
  ctx.fillStyle = "rgba(120,120,120,0.35)";
  for (let x = cx - 1; x <= cx + 1; x++) {
    for (let y = cy - 1; y <= cy + 1; y++) {
      if (x < 0 || y < 0 || x >= gridSize || y >= gridSize) continue;
      ctx.fillRect(
        x * TILE_SIZE,
        y * TILE_SIZE,
        TILE_SIZE,
        TILE_SIZE
      );
    }
  }

  /* ===============================
     Bear circle
  =============================== */
  const px = pos.x * TILE_SIZE + TILE_SIZE / 2;
  const py = pos.y * TILE_SIZE + TILE_SIZE / 2;

  // slightly smaller than 3x3 influence
  const radius = TILE_SIZE * 1.35;

  ctx.beginPath();
  ctx.arc(px, py, radius, 0, Math.PI * 2);

  // fill NEVER changes due to remote busy
  ctx.fillStyle = bear.locked ? "#1e293b" : "#0a1f44";
  ctx.fill();

  // stroke ONLY shows busy
  if (isRemoteBusy) {
    ctx.strokeStyle = "#dc2626";
    ctx.lineWidth = 3 / viewZoom;  // Scale line width
    ctx.stroke();
  }

  /* ===============================
     Bear label
  =============================== */
  ctx.save();
  ctx.translate(px, py);
  ctx.rotate(-Math.PI / 4);
  const scale = Math.min(1 + (viewZoom - 1) * 0.1, 1.2);  // Smoother, smaller max scaling
  ctx.fillStyle = "#ffffff";
  ctx.font = `bold ${Math.max(12, TILE_SIZE * 0.35) * scale}px sans-serif`;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(String(bear.id ?? ""), 0, 0);
  ctx.restore();

  /* ===============================
     IN USE label (centred)
  =============================== */
  if (isRemoteBusy) {
    ctx.save();
    ctx.translate(px, py);
    ctx.rotate(-Math.PI / 4);
    ctx.translate(0, -radius + 10);

    ctx.fillStyle = "#dc2626";
    ctx.font = `bold ${11 * scale}px sans-serif`;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";

    ctx.fillText("IN USE", 0, 20);
    ctx.restore();
  }

  // -------- Locked indicator --------
  if (bear.locked) {
    ctx.save();
    ctx.translate(px, py);
    ctx.rotate(-Math.PI / 4);

    ctx.font = `${14 * scale}px sans-serif`;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillStyle = "#ffffff";

    ctx.fillText("🔒", 0, TILE_SIZE * 0.45);
    ctx.restore();
  }
}

// function drawCastle(castle) {
//   if (!castle || castle.x == null || castle.y == null) return;
//
//   const px = castle.x * TILE_SIZE;
//   const py = castle.y * TILE_SIZE;
//   const size = TILE_SIZE * 2;
//
//   const isRemoteBusy =
//     window.remoteBusy?.has(castle.id) &&
//     draggingCastle?.id !== castle.id;
//
//   // -------- body --------
//   ctx.fillStyle = efficiencyColor(castle.efficiency ?? 99);
//   ctx.fillRect(px + 2, py + 2, size - 4, size - 4);
//
//   // -------- border --------
//   ctx.save();
//   ctx.strokeStyle = isRemoteBusy ? "#dc2626" : "#e5e7eb";
//   ctx.lineWidth = (isRemoteBusy ? 3 : 1) / viewZoom;  // Scale line width
//   ctx.strokeRect(px + 2, py + 2, size - 4, size - 4);
//   ctx.restore();
//
//   // -------- text --------
//   ctx.save();
//   ctx.translate(px + size / 2, py + size / 2);
//   ctx.rotate(-Math.PI / 4);
//
//   const scale = Math.min(1 + (viewZoom - 1) * 0.1, 1.2);  // Smoother, smaller max scaling
//   ctx.fillStyle = "white";
//   ctx.textAlign = "center";
//
//   ctx.font = `bold ${10 * scale}px sans-serif`;  // Player name
//   ctx.fillText(String(castle.player ?? ""), 0, -6);
//
//   ctx.font = `${12 * scale}px sans-serif`;  // Level
//   ctx.fillText(`Lv ${castle.player_level ?? "-"}`, 0, 10);
//
//   ctx.font = `${11 * scale}px sans-serif`;  // Preference
//   ctx.fillText(`Pref: ${castle.preference ?? ""}`, 0, 24);
//
//   if (isRemoteBusy) {
//     ctx.fillStyle = "#d90000";
//     ctx.font = `bold ${11 * scale}px sans-serif`;  // IN USE
//     ctx.fillText("IN USE", 0, -20);
//   }
//   ctx.restore();
//
//   // -------- lock icon --------
//   if (castle.locked) {
//     ctx.save();
//     ctx.translate(px + size / 2, py + size + 8);
//     ctx.rotate(-Math.PI / 4);
//     ctx.font = `${12 * scale}px sans-serif`;
//     ctx.textAlign = "center";
//     ctx.fillStyle = "white";
//     ctx.fillText("🔒", 35, 5);
//     ctx.restore();
//   }
// }

function drawCastle(castle) {
  if (!castle || castle.x == null || castle.y == null) return;

  // Use animated position if available
  const pos = getAnimatedPosition(castle);
  const px = pos.x * TILE_SIZE;
  const py = pos.y * TILE_SIZE;
  const size = TILE_SIZE * 2;

  const isRemoteBusy =
    window.remoteBusy?.has(castle.id) &&
    draggingCastle?.id !== castle.id;

  const isVisible = visibleCastleIds.size === 0 || visibleCastleIds.has(castle.id);
  if (!isVisible) {
    ctx.globalAlpha = 0.3;  // Fade non-filtered
  }

  // -------- body --------
  ctx.fillStyle = efficiencyColor(castle.efficiency ?? 99);
  ctx.fillRect(px + 2, py + 2, size - 4, size - 4);

  // -------- border --------
  ctx.save();
  ctx.strokeStyle = isRemoteBusy ? "#dc2626" : "#e5e7eb";
  ctx.lineWidth = (isRemoteBusy ? 3 : 1) / viewZoom;  // Scale line width
  ctx.strokeRect(px + 2, py + 2, size - 4, size - 4);
  ctx.restore();

  // -------- text --------
  ctx.save();
  ctx.translate(px + size / 2, py + size / 2);
  ctx.rotate(-Math.PI / 4);

  const scale = Math.min(1 + (viewZoom - 1) * 0.1, 1.2);  // Smoother, smaller max scaling
  ctx.fillStyle = "white";
  ctx.textAlign = "center";

  ctx.font = `bold ${10 * scale}px sans-serif`;  // Player name
  ctx.fillText(String(castle.player ?? ""), 0, -6);

  ctx.font = `${12 * scale}px sans-serif`;  // Level
  ctx.fillText(`Lv ${castle.player_level ?? "-"}`, 0, 10);

  ctx.font = `${11 * scale}px sans-serif`;  // Preference
  ctx.fillText(String(castle.preference ?? ""), 0, 24);

  if (isRemoteBusy) {
    ctx.fillStyle = "#d90000";
    ctx.font = `bold ${11 * scale}px sans-serif`;  // IN USE
    ctx.fillText("IN USE", 0, -20);
  }
  ctx.restore();

  // -------- lock icon --------
  if (castle.locked) {
    ctx.save();
    ctx.translate(px + size / 2, py + size + 8);
    ctx.rotate(-Math.PI / 4);
    ctx.font = `${12 * scale}px sans-serif`;
    ctx.textAlign = "center";
    ctx.fillStyle = "white";
    ctx.fillText("🔒", 35, 5);
    ctx.restore();
  }

  // Reset alpha
  ctx.globalAlpha = 1;
}

function efficiencyColor(value) {
    if (value == null) return "#374151";
    if (!mapData?.efficiency_scale) return "#374151";

    for (const tier of mapData.efficiency_scale) {
        if (value <= tier.max) {
            return tier.color;
        }
    }

    return mapData.efficiency_scale.at(-1).color;
}

function renderEfficiencyLegend() {
    const container = document.getElementById("efficiencyLegend");
    if (!container || !mapData?.efficiency_scale) return;

    container.innerHTML = "";

    mapData.efficiency_scale.forEach(tier => {
        const row = document.createElement("div");
        row.className = "legend-row";

        const swatch = document.createElement("span");
        swatch.className = "legend-swatch";
        swatch.style.background = tier.color;

        const label = document.createElement("span");
        label.textContent = tier.label;

        row.appendChild(swatch);
        row.appendChild(label);
        container.appendChild(row);
    });
}

renderEfficiencyLegend();

function onMouseDown(e) {
  if (!mapData) return;
  if (draggingCastle || draggingBear || draggingBanner) return;

  const rect = canvas.getBoundingClientRect();
  const mouseCanvasX = e.clientX - rect.left;
  const mouseCanvasY = e.clientY - rect.top;
  const { x, y } = screenToGrid(mouseCanvasX, mouseCanvasY);

  // Simple debug log
  console.log(`Mouse: (${mouseCanvasX}, ${mouseCanvasY}), Grid: (${x}, ${y}), Zoom: ${viewZoom}`);

  // ---- BEARS FIRST ----
  for (let bear of mapData.bear_traps || []) {
    if (isPointInEntity(x, y, bear)) {
      if (bear.locked) return;
      if (window.remoteBusy?.has(bear.id)) return;

      draggingBear = bear;
      bear._original = { x: bear.x, y: bear.y };

      Sync.markBusy(bear.id);  // Mark as busy for sync

      drawMap(mapData);
      return;
    }
  }

  // ---- THEN CASTLES ----
  for (let castle of mapData.castles || []) {
    if (castle.x == null || castle.y == null) continue;
    if (isPointInEntity(x, y, castle)) {
      if (castle.locked) return;
      if (window.remoteBusy?.has(castle.id)) return;

      draggingCastle = castle;
      castle._original = { x: castle.x, y: castle.y };
      castle._grab = { dx: x - castle.x, dy: y - castle.y };

      Sync.markBusy(castle.id);  // Mark as busy for sync

      drawMap(mapData);
      return;
    }
  }

  // ---- THEN BANNERS ----
  for (let banner of mapData.banners || []) {
    if (isPointInEntity(x, y, banner)) {
      if (banner.locked) return;
      if (window.remoteBusy?.has(banner.id)) return;

      draggingBanner = banner;
      banner._original = { x: banner.x, y: banner.y };

      Sync.markBusy(banner.id);  // Mark as busy for sync

      drawMap(mapData);
      return;
    }
  }

  // If no entity hit, start panning
  isPanning = true;
  lastPanX = e.clientX;
  lastPanY = e.clientY;
  canvas.style.cursor = 'grabbing';
}

function onMouseUp() {
  if (draggingCastle) {
    const c = draggingCastle;
    draggingCastle = null;

    // snap to integers ONLY for visuals
    const x = Math.round(c.x);
    const y = Math.round(c.y);

    fetch("/api/intent/move_castle", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: c.id, x, y })
    });

    Sync.unmarkBusy(c.id);
    return;
  }

  if (draggingBanner) {
    const b = draggingBanner;
    draggingBanner = null;

    const x = Math.round(b.x);
    const y = Math.round(b.y);

    fetch("/api/intent/move_banner", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: b.id, x, y })
    });

    Sync.unmarkBusy(b.id);
    return;
  }

  if (draggingBear) {
    const bear = draggingBear;
    draggingBear = null;

    const x = Math.round(bear.x);
    const y = Math.round(bear.y);

    fetch("/api/intent/move_bear_trap", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: bear.id, x, y })
    });

    Sync.unmarkBusy(bear.id);
    return;
  }
}
// function onMouseUp() {
//   if (draggingCastle) {
//     const c = draggingCastle;
//     draggingCastle = null;
//
//     // snap to integers ONLY for visuals
//     const x = Math.round(c.x);
//     const y = Math.round(c.y);
//
//     fetch("/api/intent/move_castle", {
//       method: "POST",
//       headers: { "Content-Type": "application/json" },
//       body: JSON.stringify({ id: c.id, x, y })
//     });
//
//     // Notify server: unmark as busy
//     fetch("/api/intent/unmark_busy", {
//       method: "POST",
//       headers: { "Content-Type": "application/json" },
//       body: JSON.stringify({ id: c.id })
//     }).catch(err => console.error("Failed to unmark busy:", err));
//
//     return;
//   }
//
//   if (draggingBanner) {
//     const b = draggingBanner;
//     draggingBanner = null;
//
//     const x = Math.round(b.x);
//     const y = Math.round(b.y);
//
//     fetch("/api/intent/move_banner", {
//       method: "POST",
//       headers: { "Content-Type": "application/json" },
//       body: JSON.stringify({ id: b.id, x, y })
//     });
//
//     // Notify server: unmark as busy
//     fetch("/api/intent/unmark_busy", {
//       method: "POST",
//       headers: { "Content-Type": "application/json" },
//       body: JSON.stringify({ id: b.id })
//     }).catch(err => console.error("Failed to unmark busy:", err));
//
//     return;
//   }
//
//   if (draggingBear) {
//     const bear = draggingBear;
//     draggingBear = null;
//
//     const x = Math.round(bear.x);
//     const y = Math.round(bear.y);
//
//     fetch("/api/intent/move_bear_trap", {
//       method: "POST",
//       headers: { "Content-Type": "application/json" },
//       body: JSON.stringify({ id: bear.id, x, y })
//     });
//
//     // Notify server: unmark as busy
//     fetch("/api/intent/unmark_busy", {
//       method: "POST",
//       headers: { "Content-Type": "application/json" },
//       body: JSON.stringify({ id: bear.id })
//     }).catch(err => console.error("Failed to unmark busy:", err));
//
//     return;
//   }
// }
// function onMouseDown(e) {
//   if (!mapData) return;
//   if (draggingCastle || draggingBear || draggingBanner) return;
//
//   const rect = canvas.getBoundingClientRect();
//   const mouseCanvasX = e.clientX - rect.left;
//   const mouseCanvasY = e.clientY - rect.top;
//   const { x, y } = screenToGrid(mouseCanvasX, mouseCanvasY);
//
//   // Simple debug log
//   console.log(`Mouse: (${mouseCanvasX}, ${mouseCanvasY}), Grid: (${x}, ${y}), Zoom: ${viewZoom}`);
//
//   // ---- CASTLES FIRST ----
//   for (let castle of mapData.castles || []) {
//     if (castle.x == null || castle.y == null) continue;
//     if (isPointInEntity(x, y, castle)) {
//       if (castle.locked) return;
//       if (window.remoteBusy?.has(castle.id)) return;
//
//       draggingCastle = castle;
//       castle._original = { x: castle.x, y: castle.y };
//       castle._grab = { dx: x - castle.x, dy: y - castle.y };
//
//       drawMap(mapData);
//       return;
//     }
//   }
//
//   // ---- THEN BANNERS ----
//   for (let banner of mapData.banners || []) {
//     if (isPointInEntity(x, y, banner)) {
//       if (banner.locked) return;
//       if (window.remoteBusy?.has(banner.id)) return;
//
//       draggingBanner = banner;
//       banner._original = { x: banner.x, y: banner.y };
//
//       drawMap(mapData);
//       return;
//     }
//   }
//
//   // ---- THEN BEARS ----
//   for (let bear of mapData.bear_traps || []) {
//     if (isPointInEntity(x, y, bear)) {
//       if (bear.locked) return;
//       if (window.remoteBusy?.has(bear.id)) return;
//
//       draggingBear = bear;
//       bear._original = { x: bear.x, y: bear.y };
//
//       drawMap(mapData);
//       return;
//     }
//   }
//
//   // If no entity hit, start panning
//   isPanning = true;
//   lastPanX = e.clientX;
//   lastPanY = e.clientY;
//   canvas.style.cursor = 'grabbing';
// }

function onMouseMove(e) {
    if (!mapData) return;
    if (!draggingCastle && !draggingBear && !draggingBanner) return;  // Added draggingBanner check

    const rect = canvas.getBoundingClientRect();
    const {x, y} = screenToGrid(
        e.clientX - rect.left,
        e.clientY - rect.top
    );

    // ---- CASTLE DRAG ----
    if (draggingCastle) {
        if (!draggingCastle._grab) return;

        const nx = x - draggingCastle._grab.dx;
        const ny = y - draggingCastle._grab.dy;

        // clamp to grid bounds (soft clamp)
        draggingCastle.x = Math.max(
            0,
            Math.min(mapData.grid_size - 2, nx)
        );
        draggingCastle.y = Math.max(
            0,
            Math.min(mapData.grid_size - 2, ny)
        );

        drawMap(mapData);
        return;
    }

    // ---- BANNER DRAG ----
    if (draggingBanner) {
        draggingBanner.x = Math.max(
            0,
            Math.min(mapData.grid_size - 1, x)
        );
        draggingBanner.y = Math.max(
            0,
            Math.min(mapData.grid_size - 1, y)
        );

        drawMap(mapData);
        return;
    }

    // ---- BEAR DRAG ----
    if (draggingBear) {
        draggingBear.x = Math.max(
            0,
            Math.min(mapData.grid_size - 1, x)
        );
        draggingBear.y = Math.max(
            0,
            Math.min(mapData.grid_size - 1, y)
        );

        drawMap(mapData);
    }
}

// function onMouseUp() {
//     if (draggingCastle) {
//         const c = draggingCastle;
//         draggingCastle = null;
//
//         // snap to integers ONLY for visuals
//         const x = Math.round(c.x);
//         const y = Math.round(c.y);
//
//         fetch("/api/intent/move_castle", {
//             method: "POST",
//             headers: { "Content-Type": "application/json" },
//             body: JSON.stringify({ id: c.id, x, y })
//         });
//
//         Sync.unmarkBusy(c.id);
//         return;
//     }
//
//     if (draggingBanner) {
//         const b = draggingBanner;
//         draggingBanner = null;
//
//         const x = Math.round(b.x);
//         const y = Math.round(b.y);
//
//         fetch("/api/intent/move_banner", {
//             method: "POST",
//             headers: { "Content-Type": "application/json" },
//             body: JSON.stringify({ id: b.id, x, y })
//         });
//
//         Sync.unmarkBusy(b.id);
//         return;
//     }
//
//     if (draggingBear) {
//         const bear = draggingBear;
//         draggingBear = null;
//
//         const x = Math.round(bear.x);
//         const y = Math.round(bear.y);
//
//         fetch("/api/intent/move_bear_trap", {
//             method: "POST",
//             headers: { "Content-Type": "application/json" },
//             body: JSON.stringify({ id: bear.id, x, y })
//         });
//
//         Sync.unmarkBusy(bear.id);
//         return;
//     }
// }

function onCanvasContextMenu(e) {
    e.preventDefault();
    if (!mapData) return;

    const rect = canvas.getBoundingClientRect();
    const mouseX = e.clientX;
    const mouseY = e.clientY;
    const { x, y } = screenToGrid(
        e.clientX - rect.left,
        e.clientY - rect.top
    );

    let targetEntity = null;
    let entityType = '';

    // ---- BEARS FIRST ----
    for (let bear of mapData.bear_traps || []) {
        if (isPointInEntity(x, y, bear)) {
            targetEntity = bear;
            entityType = 'bear_trap';
            break;
        }
    }

    // ---- THEN CASTLES ----
    if (!targetEntity) {
        for (let castle of mapData.castles || []) {
            if (isPointInEntity(x, y, castle)) {
                targetEntity = castle;
                entityType = 'castle';
                break;
            }
        }
    }

    // ---- THEN BANNERS ----
    if (!targetEntity) {
        for (let banner of mapData.banners || []) {
            if (isPointInEntity(x, y, banner)) {
                targetEntity = banner;
                entityType = 'banner';
                break;
            }
        }
    }

    if (!targetEntity) return;

    // Create and show context menu
    showContextMenu(mouseX, mouseY, targetEntity, entityType);
}

function showContextMenu(x, y, entity, type) {
    // Remove any existing menu
    const existing = document.getElementById('context-menu');
    if (existing) existing.remove();

    const menu = document.createElement('div');
    menu.id = 'context-menu';
    menu.style.position = 'absolute';
    menu.style.left = `${x}px`;
    menu.style.top = `${y}px`;
    menu.style.background = 'white';
    menu.style.border = '1px solid #ccc';
    menu.style.padding = '5px';
    menu.style.zIndex = '1000';
    menu.style.boxShadow = '0 2px 5px rgba(0,0,0,0.2)';
    menu.style.color = 'black';  // Added for contrast

    // Option 1: Toggle Lock
    const toggleLock = document.createElement('div');
    toggleLock.textContent = 'Toggle Lock';
    toggleLock.style.cursor = 'pointer';
    toggleLock.style.padding = '5px';
    toggleLock.onmouseover = () => toggleLock.style.background = '#f0f0f0';
    toggleLock.onmouseout = () => toggleLock.style.background = 'white';
    toggleLock.onclick = async () => {
        try {
            const response = await fetch(`/api/intent/toggle_lock_${type}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ id: entity.id })
            });
            if (!response.ok) throw new Error('Failed to toggle lock');
            // Server will broadcast update and redraw
        } catch (error) {
            console.error('Error toggling lock:', error);
        }
        menu.remove();
    };
    menu.appendChild(toggleLock);

    // Option 2: Move out of the way (castles only)
    if (type === 'castle') {
        const moveAway = document.createElement('div');
        moveAway.textContent = 'Move out of the way';
        moveAway.style.cursor = 'pointer';
        moveAway.style.padding = '5px';
        moveAway.onmouseover = () => moveAway.style.background = '#f0f0f0';
        moveAway.onmouseout = () => moveAway.style.background = 'white';
        moveAway.onclick = async () => {
            try {
                const response = await fetch('/api/intent/move_castle_away', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ id: entity.id })
                });
                if (!response.ok) throw new Error('Failed to move away');
                // Server will choose edge position, update, and redraw
            } catch (error) {
                console.error('Error moving away:', error);
            }
            menu.remove();
        };
        menu.appendChild(moveAway);
    }

    // Option 3: Cancel
    const cancel = document.createElement('div');
    cancel.textContent = 'Cancel';
    cancel.style.cursor = 'pointer';
    cancel.style.padding = '5px';
    cancel.onmouseover = () => cancel.style.background = '#f0f0f0';
    cancel.onmouseout = () => cancel.style.background = 'white';
    cancel.onclick = () => menu.remove();
    menu.appendChild(cancel);

    document.body.appendChild(menu);

    // Remove menu on click outside
    const removeMenu = (e) => {
        if (!menu.contains(e.target)) {
            menu.remove();
            document.removeEventListener('click', removeMenu);
        }
    };
    setTimeout(() => document.addEventListener('click', removeMenu), 0);
}
// ==========================
// Event Listeners
// ==========================
canvas.addEventListener("mousedown", onMouseDown);
canvas.addEventListener("mousemove", onMouseMove);
canvas.addEventListener("mouseup", onMouseUp);
canvas.addEventListener("mouseleave", onMouseUp);
canvas.addEventListener("contextmenu", onCanvasContextMenu);
// Zoom with mouse wheel
function onWheel(e) {
  e.preventDefault();
  const zoomFactor = e.deltaY > 0 ? 0.9 : 1.1;
  const newZoom = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, viewZoom * zoomFactor));

  // Zoom at cursor
  const rect = canvas.getBoundingClientRect();
  const mouseX = e.clientX - rect.left;
  const mouseY = e.clientY - rect.top;
  const worldX = (mouseX - canvas.width / 2) / viewZoom + viewOffsetX;
  const worldY = (mouseY - canvas.height / 2) / viewZoom + viewOffsetY;

  viewOffsetX = worldX - (mouseX - canvas.width / 2) / newZoom;
  viewOffsetY = worldY - (mouseY - canvas.height / 2) / newZoom;
  viewZoom = newZoom;

  drawMap(mapData);
}

// Pan with middle mouse
function onMouseDownPan(e) {
  if (e.button === 1 || e.altKey) {  // Middle click or Alt+click
    e.preventDefault();
    isPanning = true;
    lastPanX = e.clientX;
    lastPanY = e.clientY;
    canvas.style.cursor = 'grabbing';
  }
}

function onMouseMovePan(e) {
  if (isPanning) {
    const dx = e.clientX - lastPanX;
    const dy = e.clientY - lastPanY;
    viewOffsetX -= dx / viewZoom;
    viewOffsetY -= dy / viewZoom;
    lastPanX = e.clientX;
    lastPanY = e.clientY;
    drawMap(mapData);
    // Hide tooltip while panning
    hideCastleTooltip();
  } else if (!draggingCastle && !draggingBear && !draggingBanner) {
    // Detect hover over castles when not dragging or panning
    const rect = canvas.getBoundingClientRect();
    const mouseCanvasX = e.clientX - rect.left;
    const mouseCanvasY = e.clientY - rect.top;
    const { x, y } = screenToGrid(mouseCanvasX, mouseCanvasY);

    // Check if hovering over a castle
    let hoveredCastle = null;
    for (let castle of mapData?.castles || []) {
      if (castle.x == null || castle.y == null) continue;
      if (isPointInEntity(x, y, castle)) {
        hoveredCastle = castle;
        break;
      }
    }

    if (hoveredCastle) {
      hoveredCastleOnCanvas = hoveredCastle;
      showCastleTooltip(hoveredCastle, e.clientX, e.clientY);
    } else {
      if (hoveredCastleOnCanvas) {
        hoveredCastleOnCanvas = null;
        hideCastleTooltip();
      }
    }
  } else {
    // Hide tooltip while dragging
    hideCastleTooltip();
  }
}

function onMouseUpPan(e) {
  if (isPanning) {
    isPanning = false;
    canvas.style.cursor = 'default';
  }
}

// Resize on window change
function onResize() {
  drawMap(mapData);
}

// Update existing listeners

// Delete Modal Events
document.getElementById("deleteReason").addEventListener("change", (e) => {
  const otherInput = document.getElementById("deleteOther");
  if (e.target.value === "Other") {
    otherInput.style.display = "block";
  } else {
    otherInput.style.display = "none";
    otherInput.value = "";
  }
});

document.getElementById("confirmDelete").addEventListener("click", async () => {
  const modal = document.getElementById("deleteModal");
  const castleId = modal.dataset.castleId;
  const reasonSelect = document.getElementById("deleteReason").value;
  let reason = reasonSelect;
  if (reasonSelect === "Other") {
    reason = document.getElementById("deleteOther").value.trim();
    if (!reason) {
      alert("Please provide an explanation for 'Other'.");
      return;
    }
  }
  if (!reason) {
    alert("Please select or enter a reason.");
    return;
  }

  modal.classList.remove("visible");
  setTimeout(() => {
    modal.style.display = "none";
  }, 200);
  
  try {
    await fetch("/api/castles/delete", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: castleId, reason })
    });
    // SSE will update
  } catch (error) {
    alert("Failed to delete castle: " + error.message);
  }
});

document.getElementById("cancelDelete").addEventListener("click", () => {
  const modal = document.getElementById("deleteModal");
  modal.classList.remove("visible");
  setTimeout(() => {
    modal.style.display = "none";
  }, 200);
});
canvas.addEventListener("wheel", onWheel, { passive: false });
canvas.addEventListener("mousedown", onMouseDownPan);
canvas.addEventListener("mousemove", onMouseMovePan);
canvas.addEventListener("mouseup", onMouseUpPan);
canvas.addEventListener("mouseleave", () => {
  hoveredCastleOnCanvas = null;
  hideCastleTooltip();
});
window.addEventListener("resize", onResize);
document
    .getElementById("downloadBtn")
    .addEventListener("click", async () => {
        try {
            const response = await fetch('/api/download_map_image');
            if (!response.ok) throw new Error('Download failed');
            const blob = await response.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'map_image.png';  // Adjust filename as needed
            a.click();
            URL.revokeObjectURL(url);
        } catch (error) {
            console.error('Error downloading map image:', error);
            alert('Failed to download map image');
        }
    });

document.getElementById("autoPlaceBtn")
    ?.addEventListener("click", async () => {
        try {
            const response = await fetch('/api/auto_place_castles', { method: 'POST' });
            if (!response.ok) throw new Error('Auto-place failed');
            // Server will handle placement, recompute, and broadcast updates/redraws
        } catch (error) {
            console.error('Error auto-placing castles:', error);
            alert('Failed to auto-place castles');
        }
    });

document
    .getElementById("uploadCsvBtn")
    .addEventListener("click", () => {
        document.getElementById("csvUpload").click();
    });

document
    .getElementById("csvUpload")
    .addEventListener("change", async e => {
        const file = e.target.files[0];
        if (!file) return;

        const formData = new FormData();
        formData.append('csv_file', file);

        try {
            const response = await fetch('/api/upload_csv', {
                method: 'POST',
                body: formData
            });
            if (!response.ok) throw new Error('Upload failed');
            // Server will parse, merge castles, recompute priorities, and broadcast updates/redraws
        } catch (error) {
            console.error('Error uploading CSV:', error);
            alert('Failed to upload CSV');
        }

        // reset input
        e.target.value = "";
    });

// ==========================
// Table row flash animation
// ==========================
function flashTableRow(castleId) {
  const row = document.querySelector(`tr[data-castle-id="${castleId}"]`);
  if (!row) return;
  
  row.classList.remove("row-updated");
  // Force reflow to restart animation
  void row.offsetWidth;
  row.classList.add("row-updated");
  
  // Remove class after animation completes
  setTimeout(() => row.classList.remove("row-updated"), 600);
}

// ==========================
// Sync → App hooks
// ==========================
window.applyRemoteUpdate = function (update) {
  if (!mapData || !update?.id) return;

  // 1️⃣ Try castles first
  let entity = mapData.castles?.find(c => c.id === update.id);
  let isCastle = !!entity;
  
  // 2️⃣ Then bears
  if (!entity) {
    entity = mapData.bear_traps?.find(b => b.id === update.id);
  }
  
  // 3️⃣ Try banners
  if (!entity) {
    entity = mapData.banners?.find(b => b.id === update.id);
  }

  // 4️⃣ Unknown entity → ignore safely
  if (!entity) return;

  // 5️⃣ Check for position changes and start animation
  const hasPositionChange = 
    update.x != null && update.y != null &&
    (entity.x != null && entity.y != null) &&
    (update.x !== entity.x || update.y !== entity.y);
  
  if (hasPositionChange) {
    startAnimation(entity.id, entity.x, entity.y, update.x, update.y);
  }

  // 6️⃣ Apply update (efficiency comes from server)
  Object.assign(entity, update);

  // 7️⃣ Flash table row for castle updates
  if (isCastle) {
    flashTableRow(update.id);
  }

  // 8️⃣ Redraw (no local recompute)
  drawMap(mapData);
  renderCastleTable?.();
};


function applyStateToEntities(localList, remoteMap) {
  if (!localList || !remoteMap) return;

  localList.forEach(entity => {
    const remote = remoteMap[entity.id];
    if (remote) {
      Object.assign(entity, remote);
    }
  });
}


window.loadFullState = function (state) {
  if (!mapData || !state) return;

  // ---- CASTLES ----
  if (state.castles) {
    mapData.castles.forEach(c => {
      const remote = state.castles[c.id];
      if (remote) Object.assign(c, remote);
    });
  }

  // ---- BEARS ----
  if (state.bears) {
    mapData.bear_traps.forEach(b => {
      const remote = state.bears[b.id];
      if (remote) Object.assign(b, remote);
    });
  }

  drawMap(mapData);
  renderCastleTable?.();
};

const searchInput = document.getElementById("castleSearch");

if (searchInput) {
  searchInput.addEventListener("input", () => {
    renderCastleTable();
  });
}

document.getElementById("howToBtn").addEventListener("click", () => {
  alert(`
BEAR PLANNER — HOW TO USE

PLACEMENT
• Drag castles to reposition them on the grid
• Castles snap to valid tiles only
• Auto Place respects player preferences

LOCKING
• Right-click a CASTLE to lock or unlock it
• Locked castles cannot be moved or auto-placed
• Right-click a BEAR to lock or unlock its position
• If something won’t move — it is locked

AUTO PLACE
• Places strongest + committed players closest to their bear
• Players marked “both” are placed along the spine
• Existing locks are never overridden

EFFICIENCY
• Lower efficiency values are better
• Colours indicate placement quality (not errors)
• Red is reserved for server or hard lock states

TABLE
• Use search to filter instantly
• Lock All applies to already placed castles
• Unlock All clears manual locks

TIP
• Always lock bears before running Auto Place
• Lock priority players manually if required
`);
});


document.getElementById("castleLimit").addEventListener("change", renderCastleTable);

// ==========================
// Grid Toggle
// ==========================
// Load grid preference from localStorage
const savedGridPreference = localStorage.getItem('showGrid');
if (savedGridPreference !== null) {
  showGrid = savedGridPreference === 'true';
}

// Update checkbox state to match loaded preference
const gridToggleCheckbox = document.getElementById('gridToggle');
if (gridToggleCheckbox) {
  gridToggleCheckbox.checked = showGrid;

  // Add event listener for grid toggle
  gridToggleCheckbox.addEventListener('change', (e) => {
    showGrid = e.target.checked;
    localStorage.setItem('showGrid', showGrid);
    drawMap(mapData);
  });
}

// document
//   .getElementById("castleTable")
//   .addEventListener("click", e => {
//     const th = e.target.closest("th[data-sort]");
//     if (!th) return;
//     sortCastles(th.dataset.sort);
//   });

// ==========================
// Lock All / Unlock All
// ==========================
document.getElementById("lockAllBtn").addEventListener("click", async () => {
  try {
    const response = await fetch('/api/intent/lock_all_placed', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    });
    
    if (!response.ok) {
      throw new Error(`Failed to lock castles: ${response.statusText}`);
    }
    
    const result = await response.json();
    console.log(`Locked ${result.locked_count} placed castles`);
    
    // UI will update via SSE, but we can show a quick notification
    alert(`Locked ${result.locked_count} placed castle(s)`);
  } catch (error) {
    console.error('Error locking castles:', error);
    alert('Failed to lock castles. See console for details.');
  }
});

document.getElementById("unlockAllBtn").addEventListener("click", async () => {
  try {
    const response = await fetch('/api/intent/unlock_all', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    });
    
    if (!response.ok) {
      throw new Error(`Failed to unlock entities: ${response.statusText}`);
    }
    
    const result = await response.json();
    const total = result.unlocked_castles + result.unlocked_banners + result.unlocked_bear_traps;
    console.log(`Unlocked ${result.unlocked_castles} castles, ${result.unlocked_banners} banners, ${result.unlocked_bear_traps} bear traps`);
    
    // UI will update via SSE, but we can show a quick notification
    alert(`Unlocked ${total} entity/entities (${result.unlocked_castles} castles, ${result.unlocked_banners} banners, ${result.unlocked_bear_traps} bear traps)`);
  } catch (error) {
    console.error('Error unlocking entities:', error);
    alert('Failed to unlock entities. See console for details.');
  }
});

// ==========================
// Version Display
// ==========================
async function fetchAndDisplayVersion() {
  try {
    const response = await fetch('/api/version');
    const data = await response.json();
    const versionElement = document.getElementById('appVersion');
    if (versionElement && data.version) {
      versionElement.textContent = `v${data.version}`;
    }
  } catch (error) {
    console.error('Failed to fetch version:', error);
    const versionElement = document.getElementById('appVersion');
    if (versionElement) {
      versionElement.textContent = 'Version unavailable';
    }
  }
}

// ==========================
// Bulk Operations
// ==========================
function updateBulkSelectionUI() {
  const toolbar = document.getElementById('bulkOpsToolbar');
  const count = document.getElementById('bulkSelectionCount');
  const selectAllCheckbox = document.getElementById('selectAllCheckbox');

  if (selectedCastleIds.size > 0) {
    toolbar.style.display = 'flex';
    count.textContent = `${selectedCastleIds.size} selected`;
  } else {
    toolbar.style.display = 'none';
  }

  // Update select all checkbox state
  if (selectAllCheckbox) {
    const visibleCheckboxes = document.querySelectorAll('#castleTableBody input[type="checkbox"]');
    const checkedCount = Array.from(visibleCheckboxes).filter(cb => cb.checked).length;
    selectAllCheckbox.checked = visibleCheckboxes.length > 0 && checkedCount === visibleCheckboxes.length;
    selectAllCheckbox.indeterminate = checkedCount > 0 && checkedCount < visibleCheckboxes.length;
  }
}

function toggleCastleSelection(castleId, checked) {
  if (checked) {
    selectedCastleIds.add(castleId);
  } else {
    selectedCastleIds.delete(castleId);
  }
  updateBulkSelectionUI();
}

function toggleSelectAll() {
  const selectAllCheckbox = document.getElementById('selectAllCheckbox');
  const checkboxes = document.querySelectorAll('#castleTableBody input[type="checkbox"]');
  
  checkboxes.forEach(cb => {
    cb.checked = selectAllCheckbox.checked;
    const castleId = cb.dataset.castleId;
    if (selectAllCheckbox.checked) {
      selectedCastleIds.add(castleId);
    } else {
      selectedCastleIds.delete(castleId);
    }
  });
  
  updateBulkSelectionUI();
}

function clearSelection() {
  selectedCastleIds.clear();
  document.querySelectorAll('#castleTableBody input[type="checkbox"]').forEach(cb => {
    cb.checked = false;
  });
  updateBulkSelectionUI();
}

async function applyBulkUpdate() {
  if (selectedCastleIds.size === 0) {
    alert('No castles selected');
    return;
  }

  const field = document.getElementById('bulkField').value;
  if (!field) {
    alert('Please select a field to update');
    return;
  }

  let value;
  if (field === 'player_level' || field === 'command_centre_level') {
    value = parseInt(document.getElementById('bulkLevelValue').value);
    if (isNaN(value) || value < 0) {
      alert('Please enter a valid level');
      return;
    }
  } else if (field === 'preference') {
    value = document.getElementById('bulkPreferenceValue').value;
  } else if (field === 'locked') {
    value = document.getElementById('bulkLockedValue').value === 'true';
  }

  try {
    const response = await fetch('/api/castles/bulk_update', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ids: Array.from(selectedCastleIds),
        updates: { [field]: value }
      })
    });

    const result = await response.json();

    if (!response.ok) {
      throw new Error(result.detail || 'Failed to update castles');
    }

    console.log('Bulk update successful:', result);
    
    // Clear selection after successful update
    clearSelection();
    
    // Reset field selector
    document.getElementById('bulkField').value = '';
    updateBulkFieldVisibility();
    
    // Show success message
    alert(`Successfully updated ${result.updated_count} castle(s)`);
    
  } catch (error) {
    console.error('Bulk update failed:', error);
    alert(`Failed to update castles: ${error.message}`);
  }
}

function updateBulkFieldVisibility() {
  const field = document.getElementById('bulkField').value;
  
  // Hide all value inputs
  document.getElementById('bulkLevelValue').style.display = 'none';
  document.getElementById('bulkPreferenceValue').style.display = 'none';
  document.getElementById('bulkLockedValue').style.display = 'none';
  
  // Show relevant input based on field
  if (field === 'player_level' || field === 'command_centre_level') {
    document.getElementById('bulkLevelValue').style.display = 'inline-block';
  } else if (field === 'preference') {
    document.getElementById('bulkPreferenceValue').style.display = 'inline-block';
  } else if (field === 'locked') {
    document.getElementById('bulkLockedValue').style.display = 'inline-block';
  }
}

// Set up bulk operations event listeners
document.getElementById('selectAllCheckbox').addEventListener('change', toggleSelectAll);
document.getElementById('applyBulkBtn').addEventListener('click', applyBulkUpdate);
document.getElementById('clearSelectionBtn').addEventListener('click', clearSelection);
document.getElementById('bulkField').addEventListener('change', updateBulkFieldVisibility);

// Fetch version on page load
fetchAndDisplayVersion();

window.Sync = Sync;