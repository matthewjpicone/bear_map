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
let tooltipTimer = null;  // Timer for delayed tooltip display
const TOOLTIP_DELAY_MS = 1500;  // 1.5 seconds delay for canvas tooltips
let tooltipElement = null;  // Cache tooltip DOM element

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

// Prevent refresh while editing table cells
let isEditingCell = false;
let pendingSSERefresh = false;

const canvas = document.getElementById("map");
if (!canvas) throw new Error("Canvas #map not found");

// ==========================
// Toast Notification Helper
// ==========================
/**
 * Simple wrapper for showing toast notifications
 * @param {string} message - The message to display
 * @param {string} type - Type: 'success', 'error', 'warning', 'info' (default: 'info')
 */
function showToast(message, type = 'info') {
  if (window.ToastManager) {
    ToastManager.show(message, null, null, type);
  } else {
    console.warn('ToastManager not available, falling back to alert:', message);
    alert(message);
  }
}
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
let sseReloadScheduled = false;

function scheduleHardReload() {
  if (sseReloadScheduled) return;
  sseReloadScheduled = true;
  console.warn("SSE disconnected — reloading page to resync with server");
  setTimeout(() => {
    window.location.reload();
  }, 1500);
}

function initSSE() {
  if (sse) return; // prevent double-connects

  try {
    sse = new EventSource("/api/stream");

    sse.onopen = () => {
      console.log("[SSE] Connected");
      sseReloadScheduled = false; // clear any pending reload
    };

    sse.onerror = err => {
      console.warn("[SSE] Connection lost", err);
      scheduleHardReload();
    };

    // Single message handler for all events
    sse.onmessage = async evt => {
      try {
        const msg = JSON.parse(evt.data);
        console.log("[SSE] message:", evt.data);  // Log all messages

        if (msg.type === "config_update") {
          // If user is editing a table cell, defer refresh until editing completes
          if (isEditingCell) {
            pendingSSERefresh = true;
            return;
          }

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
    scheduleHardReload();
  }
}

(async () => {
  const ok = await loadMapData();
  if (!ok) return;

  // Center the rotated grid
  viewOffsetX = 0;
  viewOffsetY = (mapData.grid_size * TILE_SIZE) * (Math.SQRT2 / 2);

  // Cache tooltip element reference for better performance
  tooltipElement = document.getElementById("castleTooltip");

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
/**
 * Normalize bear trap data structure with defaults
 * @param {Object} bear - Raw bear data from server
 * @param {number} index - Index of bear in array
 * @returns {Object} Normalized bear object
 */
function normaliseBear(bear, index) {
  return {
    id: bear.id ?? `Bear ${index + 1}`,
    x: typeof bear.x === "number" ? bear.x : null,
    y: typeof bear.y === "number" ? bear.y : null,
    locked: !!bear.locked,
    size: { w: 3, h: 3, ox: 1, oy: 1 }  // 3x3 centered on (x,y)
  };
}

/**
 * Normalize castle data structure with defaults
 * @param {Object} castle - Raw castle data from server
 * @param {number} index - Index of castle in array
 * @returns {Object} Normalized castle object
 */
function normaliseCastle(castle, index) {
  return {
    id: castle.id ?? `Castle ${index + 1}`,
    player: (castle.player ?? "").substring(0, 20),  // Limit to 20 chars
    power: Number(castle.power) || 0,
    player_level: Number(castle.player_level) || 0,
    command_centre_level: Number(castle.command_centre_level) || 0,
    attendance: Number(castle.attendance) || 0,
    rallies_30min: Number(castle.rallies_30min) || 0,

    preference: castle.preference ?? "BT1/2",

    current_trap: castle.current_trap ?? null,
    recommended_trap: castle.recommended_trap ?? null,

    round_trip: typeof castle.round_trip === "number" ? castle.round_trip : "NA",

    last_updated: castle.last_updated ? new Date(castle.last_updated) : null,  // New field

    x: typeof castle.x === "number" ? castle.x : null,
    y: typeof castle.y === "number" ? castle.y : null,

    locked: !!castle.locked,
    size: { w: 2, h: 2, ox: 0, oy: 0 },  // 2x2 square from (x,y)

    // New scoring fields
    priority_score: castle.priority_score ?? null,

    priority_rank_100: castle.priority_rank_100 ?? null,

    priority_index: castle.priority_index ?? null,

    priority_debug: castle.priority_debug ?? {},

    ideal_x: castle.ideal_x ?? null,

    ideal_y: castle.ideal_y ?? null,

    ideal_travel_time: castle.ideal_travel_time ?? null,

    actual_travel_time: castle.actual_travel_time ?? null,

    regret: castle.regret ?? null,

    block_penalty_raw: castle.block_penalty_raw ?? null,

    efficiency_score: castle.efficiency_score ?? null,

    // Map score fields
    map_score_900: castle.map_score_900 ?? null,

    map_score_percent: castle.map_score_percent ?? null,

    empty_score_100: castle.empty_score_100 ?? null,

    efficiency_avg: castle.efficiency_avg ?? null,
  };
}

/**
 * Normalize banner data structure with defaults
 * @param {Object} banner - Raw banner data from server
 * @param {number} index - Index of banner in array
 * @returns {Object} Normalized banner object
 */
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
        : [],

      // Map score fields
      map_score_900: raw.map_score_900 ?? null,
      map_score_percent: raw.map_score_percent ?? null,
      empty_score_100: raw.empty_score_100 ?? null,
      efficiency_avg: raw.efficiency_avg ?? null,
      avg_round_trip: raw.avg_round_trip ?? null,
      avg_rallies: raw.avg_rallies ?? null,
    };

    mapData = config;
    window.mapData = mapData;

    updateMapScoreDisplay();

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

/**
 * Escape special regex characters in a string
 * @param {string} str - String to escape
 * @returns {string} Escaped string safe for use in RegExp
 */
function escapeRegex(str) {
  return str.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/**
 * Highlight search query within text using HTML mark tags
 * @param {string} text - Text to highlight within
 * @param {string} query - Search query to highlight
 * @returns {DocumentFragment} Document fragment with highlighted text
 */
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

/**
 * Debounce a function so it only runs after no calls for `delayMs`.
 * @param {Function} fn - Function to debounce
 * @param {number} delayMs - Delay in milliseconds
 * @returns {Function} debounced function
 */
function debounce(fn, delayMs) {
  let tId;
  return (...args) => {
    clearTimeout(tId);
    tId = setTimeout(() => fn.apply(null, args), delayMs);
  };
}

// ==========================
// Tooltip Functions
// ==========================
function showCastleTooltip(castle, mouseX, mouseY) {
  // Use cached tooltip element for performance
  if (!tooltipElement || !castle) return;

  // Format the tooltip content
  const lastUpdated = castle.last_updated 
    ? castle.last_updated.toLocaleString() 
    : "Never";

  tooltipElement.innerHTML = `
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
      <span class="tooltip-label">Last Updated:</span>
      <span class="tooltip-value">${lastUpdated}</span>
    </div>
    <div class="tooltip-row">
      <span class="tooltip-label">Locked:</span>
      <span class="tooltip-value">${castle.locked ? "Yes 🔒" : "No"}</span>
    </div>
    <div class="tooltip-row">
      <span class="tooltip-label">Priority Rank:</span>
      <span class="tooltip-value">${castle.priority_rank_100 ?? "—"}</span>
    </div>
    <div class="tooltip-row">
      <span class="tooltip-label">Efficiency Score:</span>
      <span class="tooltip-value">${castle.efficiency_score ?? "—"}</span>
    </div>
    <div class="tooltip-row">
      <span class="tooltip-label">Actual Travel Time:</span>
      <span class="tooltip-value">${castle.actual_travel_time ?? "—"}</span>
    </div>
    <div class="tooltip-row">
      <span class="tooltip-label">Ideal Travel Time:</span>
      <span class="tooltip-value">${castle.ideal_travel_time ?? "—"}</span>
    </div>
    <div class="tooltip-row">
      <span class="tooltip-label">Regret:</span>
      <span class="tooltip-value">${castle.regret ?? "—"}</span>
    </div>
  `;

  // Position the tooltip over the castle
  tooltipElement.style.display = "block";
  
  // If castle has grid coordinates, position tooltip over the castle
  if (castle.x != null && castle.y != null) {
    const screenPos = gridToScreen(castle.x, castle.y);
    tooltipElement.style.left = `${screenPos.x}px`;
    tooltipElement.style.top = `${screenPos.y}px`;
  } else {
    // Fallback to mouse position for castles not on the map
    tooltipElement.style.left = `${mouseX + 15}px`;
    tooltipElement.style.top = `${mouseY + 15}px`;
  }

  // Adjust position if tooltip goes off-screen
  const rect = tooltipElement.getBoundingClientRect();
  const offsetX = 10;
  const offsetY = 10;
  
  // Check if tooltip goes off right edge
  if (rect.right > window.innerWidth) {
    tooltipElement.style.left = `${window.innerWidth - rect.width - offsetX}px`;
  }
  // Check if tooltip goes off bottom edge
  if (rect.bottom > window.innerHeight) {
    tooltipElement.style.top = `${window.innerHeight - rect.height - offsetY}px`;
  }
  // Check if tooltip goes off left edge
  if (rect.left < 0) {
    tooltipElement.style.left = `${offsetX}px`;
  }
  // Check if tooltip goes off top edge
  if (rect.top < 0) {
    tooltipElement.style.top = `${offsetY}px`;
  }
  
  // Trigger animation after positioning
  setTimeout(() => tooltipElement.classList.add("visible"), 10);
}

function hideCastleTooltip() {
  // Use cached tooltip element for performance
  if (tooltipElement) {
    tooltipElement.classList.remove("visible");
    // Hide after animation completes
    setTimeout(() => {
      tooltipElement.style.display = "none";
    }, 150);
  }
}

// ==========================
// Input Builders
// ==========================
function createTextInput(value, onCommit) {
  const input = document.createElement("input");
  input.type = "text";
  input.value = value ?? "";
  input.size = Math.max(input.value.length, 4);

  let originalValue = input.value;

  input.addEventListener("focus", () => {
    isEditingCell = true;
  });

  input.addEventListener("input", () => {
    // Only resize input while typing; do not commit yet
    input.size = Math.max(input.value.length, 4);
  });

  function commitIfChanged() {
    const newVal = input.value;
    if (typeof onCommit === 'function' && newVal !== originalValue) {
      onCommit(newVal);
      originalValue = newVal; // update base
    }
  }

  input.addEventListener("keydown", e => {
    if (e.key === 'Enter') {
      e.preventDefault();
      commitIfChanged();
      input.blur();
    } else if (e.key === 'Escape') {
      // Revert and blur
      input.value = originalValue;
      input.blur();
    }
  });

  input.addEventListener("blur", async () => {
    // Commit on blur
    commitIfChanged();
    isEditingCell = false;
    // If a server update was deferred during editing, apply it now
    if (pendingSSERefresh) {
      pendingSSERefresh = false;
      const ok = await loadMapData();
      if (ok) {
        renderCastleTable();
        drawMap(mapData);
      }
    }
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
  if (typeof value === "number" && value >= 60) {
    // Format round trip time
    const minutes = Math.floor(value / 60);
    const seconds = value % 60;
    td.textContent = `${minutes}m ${seconds}s`;
  } else {
    td.textContent = value ?? "—";
  }
  td.style.opacity = 0.6;
  return td;
}

function tdReadonlyNumber(value) {
  const td = document.createElement("td");
  td.textContent = value ?? "—";
  td.style.opacity = 0.6;
  return td;
}

/**
 * Create a table cell for attendance with increment/decrement buttons.
 * @param {Object} castle - The castle object.
 * @returns {HTMLTableCellElement} The table cell element.
 */
function tdAttendance(castle) {
  const td = document.createElement("td");
  td.classList.add("attendance-cell");

  const container = document.createElement("div");
  container.classList.add("attendance-controls");

  // Decrement button
  const minusBtn = document.createElement("button");
  minusBtn.type = "button";
  minusBtn.classList.add("attendance-btn", "attendance-minus");
  minusBtn.textContent = "−";
  minusBtn.title = "Decrease attendance";

  // Value display
  const valueSpan = document.createElement("span");
  valueSpan.classList.add("attendance-value");
  valueSpan.textContent = castle.attendance ?? 0;

  // Increment button
  const plusBtn = document.createElement("button");
  plusBtn.type = "button";
  plusBtn.classList.add("attendance-btn", "attendance-plus");
  plusBtn.textContent = "+";
  plusBtn.title = "Increase attendance";

  // Track in-flight state to prevent spam
  let inFlight = false;

  async function adjustAttendance(delta) {
    if (inFlight) return;

    inFlight = true;
    minusBtn.disabled = true;
    plusBtn.disabled = true;

    try {
      const response = await fetch('/api/intent/adjust_attendance', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ castle_id: castle.id, delta: delta })
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to adjust attendance');
      }

      const result = await response.json();

      // Update local data
      castle.attendance = result.attendance;
      valueSpan.textContent = result.attendance;

      // Update mapData to keep in sync
      const mapCastle = mapData?.castles?.find(c => c.id === castle.id);
      if (mapCastle) {
        mapCastle.attendance = result.attendance;
      }

    } catch (error) {
      console.error('Error adjusting attendance:', error);
      showToast('Failed to adjust attendance: ' + error.message, 'error');
    } finally {
      inFlight = false;
      minusBtn.disabled = false;
      plusBtn.disabled = false;
    }
  }

  minusBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    adjustAttendance(-1);
  });

  plusBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    adjustAttendance(1);
  });

  container.appendChild(minusBtn);
  container.appendChild(valueSpan);
  container.appendChild(plusBtn);
  td.appendChild(container);

  return td;
}

function tdInput(field, obj) {
  const td = document.createElement("td");

  const input = createTextInput(obj[field], async value => {
    obj[field] = value;
    // Commit changes to server only on blur/Enter via onCommit
    await updateCastleField(obj.id, field, value);
  });

  td.appendChild(input);
  return td;
}

function tdNumber(field, obj) {
  const td = document.createElement("td");
  const input = document.createElement("input");

  input.type = "number";
  input.value = obj[field] ?? 0;

  let originalValue = String(input.value);

  input.addEventListener('focus', () => {
    isEditingCell = true;
  });

  function commitNumber() {
    const value = Number(input.value);
    if (String(value) !== originalValue) {
      originalValue = String(value);
      obj[field] = value;
      updateCastleField(obj.id, field, value);
    }
  }

  input.addEventListener('keydown', e => {
    if (e.key === 'Enter') {
      e.preventDefault();
      commitNumber();
      input.blur();
    } else if (e.key === 'Escape') {
      input.value = originalValue;
      input.blur();
    }
  });

  input.addEventListener('blur', async () => {
    commitNumber();
    isEditingCell = false;
    if (pendingSSERefresh) {
      pendingSSERefresh = false;
      const ok = await loadMapData();
      if (ok) {
        renderCastleTable();
        drawMap(mapData);
      }
    }
  });

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
//       if (typeof va === "number" ) return (va - vb) * (castleSort.asc ? 1 : -1);
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
      // Show tooltip immediately on table hover for better UX
      // Table context: User intentionally hovering over specific row to read data
      // Canvas context: 1500ms delay prevents accidental triggers during map navigation
      showCastleTooltip(c, e.clientX, e.clientY);
    });
    tr.addEventListener("mouseleave", () => {
      hoveredCastleId = null;
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
    tr.appendChild(tdSelect("preference", c, ["BT1", "BT2", "BT1/2", "BT2/1"]));
    tr.appendChild(tdCheckbox("locked", c));
    tr.appendChild(tdAttendance(c));  // Attendance with +/- buttons
    tr.appendChild(tdReadonly(c.rallies_30min));  // Read-only Rallies/Session
    tr.appendChild(tdReadonly(c.round_trip || "NA"));  // New read-only Round Trip Time (s)
    tr.appendChild(tdReadonlyNumber(c.priority_rank_100));
    tr.appendChild(tdReadonlyNumber(c.efficiency_score));
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

    ctx.font = `${12 * scale}px sans-serif`;
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
  ctx.fillStyle = efficiencyColor(castle.efficiency_score ?? 99);
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

    // Add heading
    const heading = document.createElement("h3");
    heading.textContent = "Placement Suitability";
    container.appendChild(heading);

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

  // ---- CASTLES FIRST ----
  for (let castle of mapData.castles || []) {
    if (castle.x == null || castle.y == null) continue;
    if (isPointInEntity(x, y, castle)) {
      if (castle.locked) return;
      if (window.remoteBusy?.has(castle.id)) return;

      draggingCastle = castle;
Sync.markBusy(castle.id)

      castle._original = { x: castle.x, y: castle.y };
      castle._grab = { dx: x - castle.x, dy: y - castle.y };

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
      Sync.markBusy(banner.id)
      banner._original = { x: banner.x, y: banner.y };

      drawMap(mapData);
      return;
    }
  }

  // ---- THEN BEARS ----
  for (let bear of mapData.bear_traps || []) {
    if (isPointInEntity(x, y, bear)) {
      if (bear.locked) return;
      if (window.remoteBusy?.has(bear.id)) return;

      draggingBear = bear;
      Sync.markBusy(bear.id)
      bear._original = { x: bear.x, y: bear.y };

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
    })
    .then(response => response.json())
    .then(data => {
      console.log("Castle move response:", data);
      if (!data.success) {
        ToastManager.show(data.message || data.error || "Move failed", null, "error", "error");
      } else {
        ToastManager.show("Castle moved successfully", null, "success", "success");
      }
    })
    .catch(err => {
      console.error("Move castle failed:", err);
      ToastManager.show("Move failed due to network error", null, "error", "error");
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
    })
    .then(response => response.json())
    .then(data => {
      if (!data.success) {
        ToastManager.show(data.message || data.error || "Move failed", null, "error", "error");
      } else {
        ToastManager.show("Banner moved successfully", null, "success", "success");
      }
    })
    .catch(err => {
      console.error("Move banner failed:", err);
      ToastManager.show("Move failed due to network error", null, "error", "error");
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
      body: JSON.stringify({ id: bear.id, x: x, y: y })
    })
    .then(response => response.json())
    .then(data => {
      if (!data.success) {
        ToastManager.show(data.message || data.error || "Placement failed", null, "error");
      } else {
        ToastManager.show("Bear trap placed successfully", null, "success", "success");
      }
    })
    .catch(err => {
      console.error("Move bear trap failed:", err);
      ToastManager.show("Placement failed due to network error", null, "error");
    });

    Sync.unmarkBusy(bear.id);
    return;
  }
}

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
    // Hide tooltip while panning and clear any pending timer
    clearTimeout(tooltipTimer);
    tooltipTimer = null;
    hideCastleTooltip();
    // While panning, cursor stays grabbing
    canvas.style.cursor = 'grabbing';
  } else if (!draggingCastle && !draggingBear && !draggingBanner) {
    // Detect hover over castles when not dragging or panning
    const rect = canvas.getBoundingClientRect();
    const mouseCanvasX = e.clientX - rect.left;
    const mouseCanvasY = e.clientY - rect.top;
    const { x, y } = screenToGrid(mouseCanvasX, mouseCanvasY);

    let hoveredEntity = null;

    // Check castles
    for (let castle of mapData?.castles || []) {
      if (castle.x == null || castle.y == null) continue;
      if (isPointInEntity(x, y, castle)) {
        hoveredEntity = { type: 'castle', entity: castle };
        break;
      }
    }

    // Check bears if nothing yet
    if (!hoveredEntity) {
      for (let bear of mapData?.bear_traps || []) {
        if (bear.x == null || bear.y == null) continue;
        if (isPointInEntity(x, y, bear)) {
          hoveredEntity = { type: 'bear', entity: bear };
          break;
        }
      }
    }

    // Check banners if still nothing
    if (!hoveredEntity) {
      for (let banner of mapData?.banners || []) {
        if (banner.x == null || banner.y == null) continue;
        if (isPointInEntity(x, y, banner)) {
          hoveredEntity = { type: 'banner', entity: banner };
          break;
        }
      }
    }

    // Update cursor based on hover state
    if (hoveredEntity) {
      const ent = hoveredEntity.entity;
      const isLocked = !!ent.locked;
      const isBusy = window.remoteBusy?.has(ent.id);
      if (isLocked || isBusy) {
        canvas.style.cursor = 'not-allowed';
      } else {
        // Castles show a grab cursor; other entities get a pointer
        if (hoveredEntity.type === 'castle') {
          canvas.style.cursor = 'grab';
        } else {
          canvas.style.cursor = 'pointer';
        }
      }
    } else {
      canvas.style.cursor = 'default';
    }

    // Existing tooltip handling for castles
    let hoveredCastle = hoveredEntity?.type === 'castle' ? hoveredEntity.entity : null;
    if (hoveredCastle) {
      const isTooltipVisible = tooltipElement && tooltipElement.classList.contains("visible");
      if (hoveredCastleOnCanvas !== hoveredCastle) {
        clearTimeout(tooltipTimer);
        tooltipTimer = null;
        hoveredCastleOnCanvas = hoveredCastle;
        hideCastleTooltip();
        tooltipTimer = setTimeout(() => {
          showCastleTooltip(hoveredCastle, e.clientX, e.clientY);
          tooltipTimer = null;
        }, TOOLTIP_DELAY_MS);
      } else if (isTooltipVisible) {
        showCastleTooltip(hoveredCastle, e.clientX, e.clientY);
      }
    } else {
      if (hoveredCastleOnCanvas) {
        hoveredCastleOnCanvas = null;
        clearTimeout(tooltipTimer);
        tooltipTimer = null;
        hideCastleTooltip();
      }
    }
  } else {
    // Hide tooltip while dragging and clear any pending timer
    clearTimeout(tooltipTimer);
    tooltipTimer = null;
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
  clearTimeout(tooltipTimer);
  tooltipTimer = null;
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

document
    .getElementById("jokeBtn")
    .addEventListener("click", async () => {
        try {
            const response = await fetch('https://official-joke-api.appspot.com/jokes/random');
            if (!response.ok) throw new Error('Failed to fetch joke');
            const joke = await response.json();
            document.getElementById('jokeSetup').textContent = joke.setup;
            document.getElementById('jokePunchline').textContent = joke.punchline;
            document.getElementById('jokePunchline').style.display = 'none';
            document.getElementById('jokeModal').style.display = 'block';
        } catch (error) {
            console.error('Error fetching joke:', error);
            showToast('Failed to fetch joke', 'error');
        }
    });

document
    .getElementById("revealPunchline")
    .addEventListener("click", () => {
        document.getElementById('jokePunchline').style.display = 'block';
        document.getElementById('revealPunchline').style.display = 'none';
    });

document
    .getElementById("closeJoke")
    .addEventListener("click", () => {
        document.getElementById('jokeModal').style.display = 'none';
        document.getElementById('revealPunchline').style.display = 'block';
    });

document
    .getElementById("sendToR4Btn")
    .addEventListener("click", async () => {
        try {
            const response = await fetch('/api/send_map_to_discord', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ channel: 'r4', message: 'Please review updated map' })
            });
            if (!response.ok) throw new Error('Send failed');
            showToast('Map sent to R4 on Discord! ✅', 'success');
        } catch (error) {
            console.error('Error sending map to Discord:', error);
            showToast('Failed to send map to Discord', 'error');
        }
    });

document
    .getElementById("sendToAnnouncementsBtn")
    .addEventListener("click", async () => {
        try {
            const response = await fetch('/api/send_map_to_discord', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ channel: 'announcements', message: 'New map available! Please carefully review the updated positions and make your way to your designated location when able.' })
            });
            if (!response.ok) throw new Error('Send failed');
            showToast('Map published to Announcements! ✅', 'success');
        } catch (error) {
            console.error('Error publishing map to Discord:', error);
            showToast('Failed to publish map to Discord', 'error');
        }
    });

// Publish modal logic
const publishModal = document.getElementById('publishConfirmModal');
const cancelPublishBtn = document.getElementById('cancelPublish');
const confirmPublishBtn = document.getElementById('confirmPublish');

function openPublishModal() {
  if (publishModal) publishModal.style.display = 'block';
}

function closePublishModal() {
  if (publishModal) publishModal.style.display = 'none';
}

cancelPublishBtn?.addEventListener('click', () => {
  closePublishModal();
});

confirmPublishBtn?.addEventListener('click', async () => {
  closePublishModal();
  try {
    const response = await fetch('/api/send_map_to_discord', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        channel: 'announcements',
        message: 'New map available! Please carefully review the updated positions and make your way to your designated location when able.'
      }),
    });
    if (!response.ok) throw new Error('Send failed');
    showToast('Map published to Announcements! ✅', 'success');
  } catch (error) {
    console.error('Error publishing map to Discord:', error);
    showToast('Failed to publish map to Discord', 'error');
  }
});

// Override publish button to open confirmation modal
const publishBtn = document.getElementById('sendToAnnouncementsBtn');
publishBtn?.addEventListener('click', (e) => {
  e.preventDefault();
  openPublishModal();
});

// ==========================
// Bulk Operation Modal State
// ==========================
let pendingBulkOperation = null;

/**
 * Show bulk operation confirmation modal
 * @param {string} operationType - 'autoplace' or 'moveaway'
 * @param {string} title - Modal title
 * @param {string} message - Modal message
 */
function showBulkOperationModal(operationType, title, message) {
  pendingBulkOperation = operationType;
  document.getElementById('bulkOperationTitle').textContent = title;
  document.getElementById('bulkOperationMessage').textContent = message;
  document.getElementById('bulkOperationModal').style.display = 'block';
}

/**
 * Close bulk operation modal and reset pending operation
 */
function closeBulkOperationModal() {
  document.getElementById('bulkOperationModal').style.display = 'none';
  pendingBulkOperation = null;
}

// Modal button event listeners
document.getElementById('cancelBulkOperation')?.addEventListener('click', closeBulkOperationModal);

document.getElementById('confirmBulkOperation')?.addEventListener('click', async () => {
  // Save the operation type before closing modal (which clears pendingBulkOperation)
  const operationType = pendingBulkOperation;
  closeBulkOperationModal();

  try {
    if (operationType === 'autoplace') {
      showToast('Auto-placing castles... 🚀', 'info');
      const response = await fetch('/api/auto_place_castles', { method: 'POST' });
      if (!response.ok) throw new Error('Auto-place failed');
      showToast('Castles placed successfully! ✅', 'success');
    } else if (operationType === 'moveaway') {
      showToast('Moving castles out of the way... 🚀', 'info');
      const response = await fetch('/api/move_all_out_of_way', { method: 'POST' });
      if (!response.ok) throw new Error('Move all out of way failed');
      showToast('Castles moved successfully! ✅', 'success');
    }
  } catch (error) {
    console.error('Error performing bulk operation:', error);
    showToast('Operation failed: ' + error.message, 'error');
  }
});

document.getElementById("autoPlaceBtn")
    ?.addEventListener("click", async () => {
        showBulkOperationModal(
          'autoplace',
          'Auto-Place Castles',
          'This will automatically place all unlocked castles in optimal positions based on priority and efficiency.'
        );
    });

document.getElementById("moveAllOutOfWayBtn")
    ?.addEventListener("click", async () => {
        showBulkOperationModal(
          'moveaway',
          'Move All Out of Way',
          'This will move all unlocked castles to the edge of the map to clear space for other placements.'
        );
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
  
  //  // 3️⃣ Try banners
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

  // 7️⃣ Redraw (no local recompute)
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
  const debouncedRender = debounce(() => {
    renderCastleTable();
  }, 300);
  searchInput.addEventListener("input", debouncedRender);
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

// ==========================
// Add Castle Modal Functions
// ==========================

/**
 * Open the Add Castle modal
 */
function openAddCastleModal() {
  // Clear previous inputs
  document.getElementById('addCastleName').value = '';
  document.getElementById('addCastlePower').value = '';
  document.getElementById('addCastleLevel').value = '25';
  document.getElementById('addCastlePreference').value = 'Both';

  // Show modal
  document.getElementById('addCastleModal').style.display = 'block';

  // Focus on name input
  document.getElementById('addCastleName').focus();
}

/**
 * Close the Add Castle modal
 */
function closeAddCastleModal() {
  document.getElementById('addCastleModal').style.display = 'none';
}

/**
 * Submit the Add Castle form
 */
async function submitAddCastle() {
  const playerName = document.getElementById('addCastleName').value.trim();
  const powerStr = document.getElementById('addCastlePower').value.trim();
  const levelStr = document.getElementById('addCastleLevel').value;
  const preference = document.getElementById('addCastlePreference').value;

  // Validate inputs
  if (!playerName) {
    showToast('Player name is required', 'error');
    return;
  }

  if (!powerStr) {
    showToast('Power is required', 'error');
    return;
  }

  try {
    // Parse power (handle M/K suffix)
    let power = 0;
    const powerTrimmed = powerStr.toUpperCase();
    if (powerTrimmed.endsWith('M')) {
      power = Math.floor(parseFloat(powerTrimmed) * 1000000);
    } else if (powerTrimmed.endsWith('K')) {
      power = Math.floor(parseFloat(powerTrimmed) * 1000);
    } else {
      power = parseInt(powerTrimmed);
    }

    const level = parseInt(levelStr);

    // Validate inputs
    if (isNaN(power) || power < 0) {
      showToast('Invalid power value', 'error');
      return;
    }
    if (isNaN(level) || level < 1 || level > 50) {
      showToast('Invalid level (must be 1-50)', 'error');
      return;
    }

    // Call API to create castle
    const response = await fetch('/api/castles', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        player: playerName,
        power: power,
        player_level: level,
        preference: preference
      })
    });

    if (!response.ok) {
      throw new Error('Failed to create castle');
    }

    const result = await response.json();
    showToast(`Castle added for ${playerName}! ✅`, 'success');

    // Close modal
    closeAddCastleModal();

    // Reload map data to show new castle
    await loadMapData();
    renderCastleTable();

  } catch (error) {
    console.error('Error adding castle:', error);
    showToast('Failed to add castle', 'error');
  }
}

// Add Castle button - open modal
document.getElementById("addCastleBtn")?.addEventListener("click", () => {
  openAddCastleModal();
});

// Cancel button - close modal
document.getElementById("cancelAddCastle")?.addEventListener("click", () => {
  closeAddCastleModal();
});

// Confirm button - submit form
document.getElementById("confirmAddCastle")?.addEventListener("click", async () => {
  await submitAddCastle();
});

// Enter key support in modal inputs
document.getElementById("addCastleName")?.addEventListener("keypress", (e) => {
  if (e.key === 'Enter') {
    e.preventDefault();
    document.getElementById('addCastlePower').focus();
  }
});

document.getElementById("addCastlePower")?.addEventListener("keypress", (e) => {
  if (e.key === 'Enter') {
    e.preventDefault();
    document.getElementById('addCastleLevel').focus();
  }
});

document.getElementById("addCastleLevel")?.addEventListener("keypress", async (e) => {
  if (e.key === 'Enter') {
    e.preventDefault();
    await submitAddCastle();
  }
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
    showToast(`Locked ${result.locked_count} placed castle(s)`, 'success');
  } catch (error) {
    console.error('Error locking castles:', error);
    showToast('Failed to lock castles. See console for details.', 'error');
  }
});

document.getElementById("unlockAllBtn").addEventListener("click", async () => {
  try {
    const response = await fetch('/api/intent/unlock_all', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    });
    if (!response.ok) {
      throw new Error(`Failed to unlock castles: ${response.statusText}`);
    }
    const result = await response.json();
    // Inform user
    showToast(`Unlocked ${result.unlocked_castles} castle(s)`, 'success');
  } catch (error) {
    console.error('Error unlocking castles:', error);
    showToast('Failed to unlock castles. See console for details.', 'error');
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

// ==========================
// Map Score Display
// ==========================
function updateMapScoreDisplay() {
  const display = document.getElementById('mapScoreDisplay');
  if (!display || !mapData) return;

  const score = mapData.map_score_900;
  const percent = mapData.map_score_percent;
  const empty = mapData.empty_score_100 ?? "—";
  const avg = mapData.efficiency_avg ?? "—";
  const avgRoundTrip = mapData.avg_round_trip ?? null;
  const avgRallies = mapData.avg_rallies ?? "—";

  // Format round trip time as minutes and seconds
  let roundTripDisplay = "—";
  if (avgRoundTrip != null && avgRoundTrip > 0) {
    const minutes = Math.floor(avgRoundTrip / 60);
    const seconds = avgRoundTrip % 60;
    roundTripDisplay = `${minutes}m ${seconds}s`;
  }

  console.log(`Map Score: ${score} / 900 (${percent}%)<br>Empty Tiles: ${empty} / 100<br>Avg Efficiency: ${avg}`);

  if (score != null && percent != null) {
    display.innerHTML = `
      Map Score: ${score} / 900 (${percent}%)<br>
      Tile Waste Efficiency: ${empty} / 100<br>
      Avg Efficiency Score: ${avg}<br>
      Avg Round Trip: ${roundTripDisplay}<br>
      Avg Rallies/Castle: ${avgRallies}
    `;
    // Color
    display.classList.remove('score-good', 'score-warn', 'score-bad');
    if (percent >= 80) {
      display.classList.add('score-good');
    } else if (percent >= 60) {
      display.classList.add('score-warn');
    } else {
      display.classList.add('score-bad');
    }
  } else {
    display.innerHTML = 'Map Score: —';
    display.classList.remove('score-good', 'score-warn', 'score-bad');
  }
}

// ==========================
// CSV Import/Export
// ==========================

// CSV Download
document.getElementById('downloadCsvBtn').addEventListener('click', () => {
  window.open('/api/download_csv', '_blank');
});

// CSV Upload
document.getElementById('uploadCsvBtn').addEventListener('click', () => {
  document.getElementById('csvUpload').click();
});

document.getElementById('csvUpload').addEventListener('change', async (event) => {
  const file = event.target.files[0];
  if (!file) return;

  const formData = new FormData();
  formData.append('file', file);

  try {
    const response = await fetch('/api/upload_csv', {
      method: 'POST',
      body: formData
    });
    const result = await response.json();
    if (result.success) {
      showToast(result.message, 'success');
      // Reload data
      await loadMapData();
    } else {
      showToast('Upload failed', 'error');
    }
  } catch (error) {
    showToast('Upload error', 'error');
  }
});

// ==========================
// Collapsible Panels
// ==========================

/**
 * Initialize collapsible panel functionality.
 * Manages collapse/expand for map and table panels with localStorage persistence.
 */
(function initCollapsiblePanels() {
  const STORAGE_KEY_MAP = 'bearmap_ui_mapCollapsed';
  const STORAGE_KEY_TABLE = 'bearmap_ui_tableCollapsed';

  const mapPanel = document.getElementById('mapPanel');
  const tablePanel = document.getElementById('tablePanel');
  const collapseMapBtn = document.getElementById('collapseMapBtn');
  const collapseTableBtn = document.getElementById('collapseTableBtn');

  if (!mapPanel || !tablePanel || !collapseMapBtn || !collapseTableBtn) {
    console.warn('Collapsible panel elements not found');
    return;
  }

  /**
   * Toggle the collapsed state of a panel.
   * @param {HTMLElement} panel - The panel element.
   * @param {HTMLElement} btn - The toggle button.
   * @param {string} storageKey - localStorage key for persistence.
   * @param {Function} [onExpand] - Optional callback when panel expands.
   */
  function togglePanel(panel, btn, storageKey, onExpand) {
    const isCollapsed = panel.classList.toggle('collapsed');

    // Update button aria attributes
    btn.setAttribute('aria-expanded', !isCollapsed);
    btn.setAttribute('aria-label', isCollapsed ? 'Expand panel' : 'Collapse panel');

    // Persist state
    localStorage.setItem(storageKey, isCollapsed ? '1' : '0');

    // Callback when expanding
    if (!isCollapsed && onExpand) {
      // Use double requestAnimationFrame to ensure layout is updated
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          onExpand();
        });
      });
    }
  }

  /**
   * Restore panel state from localStorage on page load.
   */
  function restoreState() {
    const mapCollapsed = localStorage.getItem(STORAGE_KEY_MAP) === '1';
    const tableCollapsed = localStorage.getItem(STORAGE_KEY_TABLE) === '1';

    if (mapCollapsed) {
      mapPanel.classList.add('collapsed');
      collapseMapBtn.setAttribute('aria-expanded', 'false');
      collapseMapBtn.setAttribute('aria-label', 'Expand panel');
    }

    if (tableCollapsed) {
      tablePanel.classList.add('collapsed');
      collapseTableBtn.setAttribute('aria-expanded', 'false');
      collapseTableBtn.setAttribute('aria-label', 'Expand panel');
    }
  }

  /**
   * Redraw the map canvas after expanding.
   */
  function redrawMapCanvas() {
    if (typeof drawMap === 'function' && mapData) {
      drawMap(mapData);
    }
  }

  // Attach click handlers
  collapseMapBtn.addEventListener('click', () => {
    togglePanel(mapPanel, collapseMapBtn, STORAGE_KEY_MAP, redrawMapCanvas);
  });

  collapseTableBtn.addEventListener('click', () => {
    togglePanel(tablePanel, collapseTableBtn, STORAGE_KEY_TABLE);
  });

  // Restore state on load
  restoreState();

  // Handle window resize - redraw map if visible
  let resizeTimer;
  window.addEventListener('resize', () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => {
      if (!mapPanel.classList.contains('collapsed') && typeof drawMap === 'function' && mapData) {
        drawMap(mapData);
      }
    }, 150);
  });
})();

