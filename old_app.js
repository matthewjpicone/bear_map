// // let draggingBear = null;
// // let draggingCastle = null;
// // const TOP_N = 7;
// // let mapData = null;
// //
// // window.remoteBusy = new Set();
// //
// // const canvas = document.getElementById("map");
// // if (!canvas) {
// //     throw new Error("Canvas #map not found");
// // }
// // const ctx = canvas.getContext("2d");
// //
// // const TILE_SIZE = 40;
// //
// // const WEIGHTS = {
// //     power: 0.45,
// //     level: 0.15,
// //     cc: 0.15,
// //     rally: 0.15,
// //     attendance: 0.10
// // };
// //
// // let castleSort = {
// //     key: null,
// //     asc: true
// // };
//
// let draggingBear = null;        // mouse interaction only
// let draggingCastle = null;     // mouse interaction only
// let mapData = null;            // hydrated from server, mutated locally for UI
// let castleSort = {             // table UI concern
//   key: null,
//   asc: true
// };
//
// window.remoteBusy = new Set(); // sync / optimistic UI guard
//
// const canvas = document.getElementById("map");
// if (!canvas) throw new Error("Canvas #map not found");
// const ctx = canvas.getContext("2d");
//
// const TILE_SIZE = 40;          // render-only constant
//
//
// // ======  Migrated ====
//
//
// fetch("/api/map")
//     .then(res => {
//         if (!res.ok) {
//             throw new Error(`API /api/map failed: ${res.status}`);
//         }
//         return res.json();
//     })
//     .then(config => {
//
//         // ---- top-level safety defaults ----
//         config.castles ??= [];
//         config.bear_traps ??= [];
//         config.banners ??= [];
//
//         // ---- backward compatibility ----
//         config.bear_traps.forEach((b, i) => {
//             if (!b.id) b.id = `Bear ${i + 1}`;
//             if (b.locked === undefined) b.locked = false;
//         });
//
//         config.castles.forEach((c, i) => {
//             if (!c.id) c.id = `Castle ${i + 1}`;
//             if (c.locked === undefined) c.locked = false;
//             if (c.efficiency === undefined) c.efficiency = null;
//             if (c.priority === undefined) c.priority = null;
//             if (typeof c.x !== "number") c.x = null;
//             if (typeof c.y !== "number") c.y = null;
//         });
//
//         // ---- AUTHORITATIVE STATE ----
// mapData = config;
// window.mapData = mapData;
//
//         fetch("/api/recompute/priorities", { method: "POST" });
//         renderCastleTable();
//         drawMap(mapData);
//
//         if (window.Sync?.init) {
//             Sync.init();
//         }
//     })
//     .catch(err => {
//         console.error(err);
//         alert("Failed to load map data from server");
//     });
//
// // ==========================
// // Utility
// // ==========================
// function autosaveCastle(castle, fields = null) {
//     if (!castle || !castle.id) return;
//     if (!window.Sync?.scheduleUpdate) return;
//
//     const payload = {id: castle.id};
//
//     // Only send explicitly allowed fields
//     const allowed = fields ?? [
//         "x",
//         "y",
//         "locked",
//         "preference",
//         "power",
//         "player_level",
//         "command_centre_level",
//         "attendance",
//         "rallies_30min",
//         "priority",
//         "efficiency"
//     ];
//
//     for (const key of allowed) {
//         if (castle[key] !== undefined) {
//             payload[key] = castle[key];
//         }
//     }
//
//     // No-op guard: don’t send empty updates
//     if (Object.keys(payload).length === 1) return;
//
//     Sync.scheduleUpdate(payload);
// }
//
// function autosaveBear(bear, fields = null) {
//   if (!bear || !bear.id) return;
//   if (!window.Sync?.scheduleUpdate) return;
//
//   const payload = { id: bear.id };
//
//   const allowed = fields ?? ["x", "y", "locked"];
//
//   for (const key of allowed) {
//     if (bear[key] !== undefined) {
//       payload[key] = bear[key];
//     }
//   }
//
//   if (Object.keys(payload).length === 1) return;
//
//   Sync.scheduleUpdate(payload);
// }
//
// function saveMap() {
//     if (!mapData) return;
//     if (!validateCastles(mapData.castles)) return;
//
//     const payload = {
//         grid_size: mapData.grid_size,
//         banner_rows: mapData.banner_rows,
//         banner_spacing: mapData.banner_spacing,
//         row_spacing: mapData.row_spacing,
//
//         banners: mapData.banners,
//         bear_traps: mapData.bear_traps,
//
//         castles: mapData.castles.map(exportCastle)
//     };
//
//     fetch("/api/save", {
//         method: "POST",
//         headers: {"Content-Type": "application/json"},
//         body: JSON.stringify(payload)
//     })
//         .then(() => alert("Layout saved"))
//         .catch(err => {
//             console.error(err);
//             alert("Save failed");
//         });
// }
//
// function parseCSV(text) {
//     const [headerLine, ...lines] = text.trim().split("\n");
//     const headers = headerLine.split(",");
//
//     return lines.map(line => {
//         const values = line.split(",");
//         const obj = {};
//         headers.forEach((h, i) => {
//             obj[h.trim()] = values[i]?.trim() ?? "";
//         });
//         return obj;
//     });
// }
//
// function castlesFromCSV(csvText) {
//     const rows = parseCSV(csvText);
//
//     return rows.map((row, index) => ({
//         id: `Castle ${index + 1}`,
//         player: row.player_id,
//
//         power: Number(row.power),
//         player_level: Number(row.player_level),
//         command_centre_level: Number(row.command_centre_level),
//
//         attendance: Number(row.attendance_count),
//         rallies_30min: Number(row.rallies_30min),
//
//         preference:
//             row.trap_preference === "1" ? "Bear 1" :
//                 row.trap_preference === "2" ? "Bear 2" :
//                     "both",
//
//         current_trap: row.current_trap || null,
//         recommended_trap: row.recommended_trap || null,
//
//         priority: null,      // computed later
//         efficiency: null,
//
//         x: row.x ? Number(row.x) : null,
//         y: row.y ? Number(row.y) : null,
//
//         locked: row.locked === "true"
//     }));
// }
//
// function mergeCastles(configCastles, csvCastles) {
//     const byPlayer = Object.fromEntries(
//         configCastles.map(c => [c.player, c])
//     );
//
//     return csvCastles.map(castle => {
//         const existing = byPlayer[castle.player];
//         if (!existing) return castle;
//
//         return {
//             ...castle,
//             x: existing.x ?? castle.x,
//             y: existing.y ?? castle.y,
//             locked: existing.locked ?? castle.locked
//         };
//     });
// }
//
// function exportCastle(c) {
//     return {
//         id: c.id,
//         player: c.player,
//
//         // stats
//         power: c.power,
//         player_level: c.player_level,
//         command_centre_level: c.command_centre_level,
//         attendance: c.attendance,
//         rallies_30min: c.rallies_30min,
//
//         // placement logic
//         preference: c.preference,
//         current_trap: c.current_trap ?? null,
//         recommended_trap: c.recommended_trap ?? null,
//         priority: c.priority,
//         efficiency: c.efficiency,
//
//         // spatial
//         x: c.x,
//         y: c.y,
//         locked: !!c.locked
//     };
// }
//
// function downloadMapImage() {
//     if (!mapData) return;
//
//     const size = mapData.grid_size;
//     const mapPixelSize = size * TILE_SIZE;
//
//     // High-res export (2× scale for clarity)
//     const SCALE = 2;
//
//     const exportCanvas = document.createElement("canvas");
//     exportCanvas.width = mapPixelSize * SCALE;
//     exportCanvas.height = mapPixelSize * SCALE;
//
//     const exportCtx = exportCanvas.getContext("2d");
//     exportCtx.scale(SCALE, SCALE);
//
//     // ---- DRAW EXACT SAME MAP ----
//     exportCtx.clearRect(0, 0, mapPixelSize, mapPixelSize);
//
//     const center = mapPixelSize / 2;
//
//     exportCtx.save();
//     exportCtx.translate(mapPixelSize / 2, mapPixelSize / 2);
//     exportCtx.rotate(Math.PI / 4);
//     exportCtx.translate(-center, -center);
//
//     // grid
//     for (let x = 0; x < size; x++) {
//         for (let y = 0; y < size; y++) {
//             exportCtx.strokeStyle = "#ccc";
//             exportCtx.strokeRect(
//                 x * TILE_SIZE,
//                 y * TILE_SIZE,
//                 TILE_SIZE,
//                 TILE_SIZE
//             );
//         }
//     }
//
//     mapData.banners.forEach(b => drawBannerExport(exportCtx, b));
//     mapData.bear_traps.forEach(b => drawBearTrapExport(exportCtx, b));
//     mapData.castles.forEach(c => drawCastleExport(exportCtx, c));
//
//     exportCtx.restore();
//
//     // ---- DOWNLOAD ----
//     const link = document.createElement("a");
//     link.download = "bear-placement.png";
//     link.href = exportCanvas.toDataURL("image/png");
//     link.click();
// }
//
// function drawBannerExport(ctx, banner) {
//     const px = banner.x * TILE_SIZE;
//     const py = banner.y * TILE_SIZE;
//
//     ctx.fillStyle = "#1e3a8a";
//     ctx.fillRect(px, py, TILE_SIZE, TILE_SIZE);
//     ctx.strokeStyle = "#fff";
//     ctx.strokeRect(px, py, TILE_SIZE, TILE_SIZE);
//
//     ctx.save();
//     ctx.translate(px + TILE_SIZE / 2, py + TILE_SIZE / 2);
//     ctx.rotate(-Math.PI / 4);
//     ctx.fillStyle = "white";
//     ctx.font = "bold 14px sans-serif";
//     ctx.textAlign = "center";
//     ctx.textBaseline = "middle";
//     ctx.fillText(banner.id, 0, 0);
//     ctx.restore();
// }
//
// function drawBearTrapExport(ctx, bear) {
//     const cx = bear.x;
//     const cy = bear.y;
//
//     // influence
//     for (let x = cx - 1; x <= cx + 1; x++) {
//         for (let y = cy - 1; y <= cy + 1; y++) {
//             if (
//                 x < 0 || y < 0 ||
//                 x >= mapData.grid_size ||
//                 y >= mapData.grid_size
//             ) continue;
//
//             ctx.fillStyle = "rgba(120,120,120,0.35)";
//             ctx.fillRect(
//                 x * TILE_SIZE,
//                 y * TILE_SIZE,
//                 TILE_SIZE,
//                 TILE_SIZE
//             );
//         }
//     }
//
//     const px = cx * TILE_SIZE + TILE_SIZE / 2;
//     const py = cy * TILE_SIZE + TILE_SIZE / 2;
//     const r = TILE_SIZE * 1.45;
//
//     ctx.fillStyle = bear.locked ? "#1e293b" : "#0a1f44";
//     ctx.beginPath();
//
//     for (let i = 0; i < 6; i++) {
//         const a = Math.PI / 3 * i;
//         const hx = px + r * Math.cos(a);
//         const hy = py + r * Math.sin(a);
//         i === 0 ? ctx.moveTo(hx, hy) : ctx.lineTo(hx, hy);
//     }
//
//     ctx.closePath();
//     ctx.fill();
//
//     ctx.save();
//     ctx.translate(px, py);
//     ctx.rotate(-Math.PI / 4);
//     ctx.fillStyle = "white";
//     ctx.font = "bold 14px sans-serif";
//     ctx.textAlign = "center";
//     ctx.textBaseline = "middle";
//     ctx.fillText(bear.id, 0, 0);
//     ctx.restore();
// }
//
// function drawCastleExport(ctx, castle) {
//     const px = castle.x * TILE_SIZE;
//     const py = castle.y * TILE_SIZE;
//     const size = TILE_SIZE * 2;
//
//
//     ctx.fillStyle = castle.locked
//         ? "#374151"
//         : efficiencyColor(castle.efficiency ?? 99);
//
//     ctx.fillRect(px + 2, py + 2, size - 4, size - 4);
//     ctx.strokeStyle = "#e5e7eb";
//     ctx.strokeRect(px + 2, py + 2, size - 4, size - 4);
//
//     ctx.save();
//     ctx.translate(px + size / 2, py + size / 2);
//     ctx.rotate(-Math.PI / 4);
//     ctx.fillStyle = "white";
//     ctx.textAlign = "center";
//     ctx.font = "bold 13px sans-serif";
//     ctx.fillText(castle.player, 0, -6);
//     ctx.font = "12px sans-serif";
//     ctx.fillText(`Lv ${castle.player_level}`, 0, 10);
//     ctx.font = "11px sans-serif";
//     ctx.fillText(`E:${castle.efficiency}`, 0, 24);
//     ctx.restore();
// }
//
// // ==========================
// // Calculation
// // ==========================
// function computePriorities(castles) {
//     const stats = {
//         power: castles.map(c => c.power),
//         level: castles.map(c => c.player_level),
//         cc: castles.map(c => c.command_centre_level),
//         attendance: castles.map(c => c.attendance),
//         rally: castles.map(c => c.rallies_30min)
//     };
//
//     const ranges = {};
//     for (let k in stats) {
//         ranges[k] = {
//             min: Math.min(...stats[k]),
//             max: Math.max(...stats[k])
//         };
//     }
//
//     castles.forEach(c => {
//         const score =
//             normalize(c.power, ranges.power.min, ranges.power.max) * WEIGHTS.power +
//             normalize(c.player_level, ranges.level.min, ranges.level.max) * WEIGHTS.level +
//             normalize(c.command_centre_level, ranges.cc.min, ranges.cc.max) * WEIGHTS.cc +
//             normalize(c.attendance, ranges.attendance.min, ranges.attendance.max) * WEIGHTS.attendance +
//             normalize(c.rallies_30min, ranges.rally.min, ranges.rally.max) * WEIGHTS.rally;
//
//         // scale to something human-readable (0–100)
//         c.priority = Math.round(score * 100);
//     });
// }
//
// function normalize(value, min, max) {
//     if (max === min) return 0;
//     return (value - min) / (max - min);
// }
//
// function manhattan(a, b) {
//     return Math.abs(a.x - b.x) + Math.abs(a.y - b.y);
// }
//
// function calculateEfficiency(castle, bears) {
//     const availableBears = Array.isArray(bears) ? bears : [];
//     const preference = (castle.preference || "both").toString().toLowerCase();
//
//     if (preference === "both") {
//         const distances = availableBears.map(b => manhattan(castle, b));
//         if (!distances.length) return Infinity;
//         return distances.reduce((sum, dist) => sum + dist, 0) / distances.length;
//     }
//
//     if (typeof castle.preference === "string") {
//         const bear = availableBears.find(
//             b => b.id?.toString().toLowerCase() === preference
//         );
//         return bear ? manhattan(castle, bear) : Infinity;
//     }
//
//     // Weighted preference (future-proof)
//     let score = 0;
//     for (let pref of castle.preference) {
//         const bear = availableBears.find(
//             b => b.id?.toString().toLowerCase() === pref.bear?.toString().toLowerCase()
//         );
//         if (bear) {
//             score += pref.weight * manhattan(castle, bear);
//         }
//     }
//     return score;
// }
//
// function generateRelocationPlan() {
//     const before = mapData.castles.map(c => ({
//         id: c.id,
//         x: c.x,
//         y: c.y,
//         priority: c.priority,
//         locked: c.locked
//     }));
//
//     // Clone state
//     const snapshot = JSON.parse(JSON.stringify(mapData));
//
//     // // Run placement on clone
//     const original = mapData;
//     mapData = snapshot;
//     autoPlaceCastles.call({mapData: snapshot});
//     mapData = original;
//
//     const moves = [];
//
//     snapshot.castles.forEach(c => {
//         const original = before.find(o => o.id === c.id);
//         if (!original || original.locked) return;
//
//         if (original.x !== c.x || original.y !== c.y) {
//             moves.push({
//                 castle: c.id,
//                 from: {x: original.x, y: original.y},
//                 to: {x: c.x, y: c.y},
//                 priority: c.priority
//             });
//         }
//     });
//
//     return moves.sort((a, b) => b.priority - a.priority);
// }
//
//
//
//
//
//
//
//
//
//
//
//
//
// function lockAllPlaced() {
//     if (!mapData) return;
//
//     mapData.castles.forEach(c => {
//         if (c.x != null && c.y != null) c.locked = true;
//     });
//
//     drawMap(mapData);
// }
//
// function unlockAll() {
//     if (!mapData) return;
//
//     mapData.castles.forEach(c => {
//         c.locked = false;
//     });
//
//     drawMap(mapData);
// }
//
// function sortCastles(key) {
//     if (!mapData || !Array.isArray(mapData.castles)) return;
//
//     // toggle direction
//     if (castleSort.key === key) {
//         castleSort.asc = !castleSort.asc;
//     } else {
//         castleSort.key = key;
//         castleSort.asc = true;
//     }
//
//     const dir = castleSort.asc ? 1 : -1;
//
//     mapData.castles.sort((a, b) => {
//         let va = a[key];
//         let vb = b[key];
//
//         // nulls always last
//         if (va == null && vb == null) return 0;
//         if (va == null) return 1;
//         if (vb == null) return -1;
//
//         // booleans
//         if (typeof va === "boolean") {
//             return (va === vb ? 0 : va ? 1 : -1) * dir;
//         }
//
//         // numbers
//         if (typeof va === "number") {
//             return (va - vb) * dir;
//         }
//
//         // fallback to string compare
//         return va.toString().localeCompare(vb.toString()) * dir;
//     });
//
//     // purely visual updates
//     renderCastleTable();
//     updateSortIndicators();
// }
//
// function enableTableSorting() {
//     const headers = document.querySelectorAll("#castleTable th[data-sort]");
//     if (!headers.length) return;
//
//     headers.forEach(th => {
//         th.style.cursor = "pointer";
//
//         // 🔁 prevent duplicate handlers
//         th.onclick = null;
//
//         th.onclick = () => {
//             sortCastles(th.dataset.sort);
//         };
//     });
// }
//
// enableTableSorting();
//
// updateSortIndicators();
//
// // ==========================
// // Validation
// // ==========================
// function isPointInCastle(gx, gy, castle) {
//     return (
//         gx >= castle.x &&
//         gx < castle.x + 2 &&
//         gy >= castle.y &&
//         gy < castle.y + 2
//     );
// }
//
// function isCastleInBounds(c, g) {
//     return c.x >= 0 && c.y >= 0 && c.x + 1 < g && c.y + 1 < g;
// }
//
// function overlapsCastle(castle, castles) {
//     const myTiles = getCastleTiles(castle);
//
//     for (let other of castles) {
//         if (other === castle) continue;
//
//         const otherTiles = getCastleTiles(other);
//
//         for (let t1 of myTiles) {
//             for (let t2 of otherTiles) {
//                 if (t1.x === t2.x && t1.y === t2.y) {
//                     return true; // actual overlap
//                 }
//             }
//         }
//     }
//     return false;
// }
//
// function overlapsBanner(bear, banners) {
//     return banners.some(b =>
//         b.x >= bear.x - 1 && b.x <= bear.x + 1 &&
//         b.y >= bear.y - 1 && b.y <= bear.y + 1
//     );
// }
//
// function overlapsBannerCastle(castle, banners) {
//     const tiles = getCastleTiles(castle);
//
//     for (let banner of banners) {
//         for (let tile of tiles) {
//             if (tile.x === banner.x && tile.y === banner.y) {
//                 return true;
//             }
//         }
//     }
//     return false;
// }
//
// function overlapsBearCastle(castle, bears) {
//     const castleTiles = getCastleTiles(castle);
//
//     for (let bear of bears) {
//         for (let dx = -1; dx <= 1; dx++) {
//             for (let dy = -1; dy <= 1; dy++) {
//                 const bx = bear.x + dx;
//                 const by = bear.y + dy;
//
//                 for (let tile of castleTiles) {
//                     if (tile.x === bx && tile.y === by) {
//                         return true;
//                     }
//                 }
//             }
//         }
//     }
//     return false;
// }
//
// function overlapsOtherBear(bear, bears) {
//     return bears.some(o =>
//         o !== bear &&
//         Math.abs(bear.x - o.x) <= 2 &&
//         Math.abs(bear.y - o.y) <= 2
//     );
// }
//
// function canPlaceCastle(x, y, occupied, gridSize) {
//     if (x < 0 || y < 0 || x + 1 >= gridSize || y + 1 >= gridSize) {
//         return false;
//     }
//
//     for (let dx = 0; dx < 2; dx++) {
//         for (let dy = 0; dy < 2; dy++) {
//             if (occupied.has(`${x + dx},${y + dy}`)) {
//                 return false;
//             }
//         }
//     }
//     return true;
// }
//
// function occupyCastle(x, y, occupied) {
//     for (let dx = 0; dx < 2; dx++) {
//         for (let dy = 0; dy < 2; dy++) {
//             occupied.add(`${x + dx},${y + dy}`);
//         }
//     }
// }
//
// function generateCandidateTiles(bear, gridSize) {
//     const tiles = [];
//     for (let x = 0; x < gridSize; x++) {
//         for (let y = 0; y < gridSize; y++) {
//             const d = Math.abs(x - bear.x) + Math.abs(y - bear.y);
//             tiles.push({x, y, d});
//         }
//     }
//     return tiles.sort((a, b) => a.d - b.d);
// }
//
// function violatesOppositeBear(x, y, role, bears) {
//     if (role === "both") return false;
//
//     const opposite =
//         role === "bear1"
//             ? bears.find(b => b.id === "Bear 2")
//             : bears.find(b => b.id === "Bear 1");
//
//     if (!opposite) return false;
//
//     // same 3x3 logic you already use elsewhere
//     for (let dx = -1; dx <= 1; dx++) {
//         for (let dy = -1; dy <= 1; dy++) {
//             if (x === opposite.x + dx && y === opposite.y + dy) {
//                 return true;
//             }
//         }
//     }
//
//     return false;
// }
//
//
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
// const EFFICIENCY_SCALE = [
//   {
//     max: 6,
//     color: "#16a34a",        // strong, confident green
//     class: "eff-excellent",
//     label: "Excellent (Best Placement)"
//   },
//   {
//     max: 10,
//     color: "#2563eb",        // clear, readable blue
//     class: "eff-good",
//     label: "Good Placement"
//   },
//   {
//     max: 15,
//     color: "#64748b",        // slate / warning-neutral
//     class: "eff-poor",
//     label: "Poor Placement"
//   },
//   {
//     max: Infinity,
//     color: "#1f2937",        // deep slate / near-black
//     class: "eff-bad",
//     label: "Bad (Worst Placement)"
//   }
// ];
//
//
//
// function efficiencyColor(e) {
//   const value = Number(e);
//   const bucket = EFFICIENCY_SCALE.find(b => value <= b.max);
//   return bucket?.color ?? "#475569";
// }
//
// function renderEfficiencyLegend() {
//   const legend = document.getElementById("efficiencyLegend");
//   if (!legend) return;
//
//   legend.innerHTML = "";
//
//   EFFICIENCY_SCALE.forEach(bucket => {
//     const row = document.createElement("div");
//     row.className = "legend-row";
//
//     const swatch = document.createElement("span");
//     swatch.className = "legend-swatch";
//     swatch.style.background = bucket.color;
//
//     const label = document.createElement("span");
//     label.textContent = bucket.label;
//
//     row.appendChild(swatch);
//     row.appendChild(label);
//     legend.appendChild(row);
//   });
// }
// renderEfficiencyLegend();
//
//
//
//
//
//
//
// function autoPlaceCastles() {
//     const failed = [];
//     const gridSize = mapData.grid_size;
//     const castles = mapData.castles;
//     const bears = mapData.bear_traps;
//
//     const occupied = new Set();
//
//     // banners
//     mapData.banners.forEach(b =>
//         occupied.add(`${b.x},${b.y}`)
//     );
//
//     // bears (3×3 influence)
//     bears.forEach(b => {
//         for (let dx = -1; dx <= 1; dx++) {
//             for (let dy = -1; dy <= 1; dy++) {
//                 occupied.add(`${b.x + dx},${b.y + dy}`);
//             }
//         }
//     });
//
//     // locked castles
//     castles.forEach(c => {
//         if (c.locked && c.x != null && c.y != null) {
//             occupyCastle(c.x, c.y, occupied);
//         }
//     });
//
//     const movable = castles
//         .filter(c => !c.locked)
//         .sort((a, b) => b.priority - a.priority);
//
// // ---- PHASE 1: TOP-N PER ROLE ----
//     const roles = ["bear1", "bear2", "both"];
//
//     for (let role of roles) {
//         movable
//             .filter(c => getCastleRole(c) === role)
//             .slice(0, TOP_N)
//             .forEach(castle => {
//                 const placement = findBestPlacement(
//                     castle,
//                     role,
//                     bears,
//                     occupied,
//                     gridSize
//                 );
//
//                 if (!placement) return;
//
//                 castle.x = placement.x;
//                 castle.y = placement.y;
//                 occupyCastle(castle.x, castle.y, occupied);
//                 castle._placed = true;
//             });
//     }
//
// // ---- PHASE 2: EVERYONE ELSE ----
//     movable
//         .filter(c => !c._placed)
//         .forEach(castle => {
//             const role = getCastleRole(castle);
//
//             let placement = findBestPlacement(
//                 castle,
//                 role,
//                 bears,
//                 occupied,
//                 gridSize
//             );
//
//             if (!placement) {
//                 placement = findAnyPlacement(occupied, gridSize);
//             }
//
//             if (!placement) return;
//
//             castle.x = placement.x;
//             castle.y = placement.y;
//             occupyCastle(castle.x, castle.y, occupied);
//         });
//
//
//     // ---- FORCE COMPRESSION PASS ----
//     compactCastles(castles, bears, occupied, gridSize);
//
//     // update efficiency
//     castles.forEach(c => {
//         c.efficiency = calculateEfficiency(c, bears);
//     });
//
//     drawMap(mapData);
//     renderCastleTable();
//
//     if (failed.length) {
//         console.warn("Unplaced castles (true grid exhaustion):", failed.map(c => c.id));
//         alert(`${failed.length} castles could not be placed. Grid is genuinely full.`);
//     }
//     mapData.castles.forEach(c => {
//         autosaveCastle(c, ["x", "y", "efficiency"]);
//     });
//
// }
//
// function getGravityTarget(role, bears) {
//     if (!Array.isArray(bears)) return null;
//
//     const b1 = bears.find(b => b.id === "Bear 1");
//     const b2 = bears.find(b => b.id === "Bear 2");
//
//     // hard guard — never explode
//     if (!b1 || !b2) return null;
//
//     if (role === "bear1") return {x: b1.x, y: b1.y};
//     if (role === "bear2") return {x: b2.x, y: b2.y};
//
//     // BOTH → midpoint
//     return {
//         x: Math.round((b1.x + b2.x) / 2),
//         y: Math.round((b1.y + b2.y) / 2)
//     };
// }
//
// function generateRingTiles(cx, cy, radius, gridSize) {
//     const tiles = [];
//
//     for (let dx = -radius; dx <= radius; dx++) {
//         const dy = radius - Math.abs(dx);
//
//         const candidates = [
//             {x: cx + dx, y: cy + dy},
//             {x: cx + dx, y: cy - dy}
//         ];
//
//         for (let t of candidates) {
//             if (
//                 t.x >= 0 &&
//                 t.y >= 0 &&
//                 t.x < gridSize &&
//                 t.y < gridSize
//             ) {
//                 tiles.push(t);
//             }
//         }
//     }
//
//     return tiles;
// }
//
// function findClosestPlacement(castle, bear, occupied, gridSize) {
//     const maxRadius = gridSize * 2;
//
//     for (let r = 0; r <= maxRadius; r++) {
//         const ring = generateRingTiles(bear.x, bear.y, r, gridSize);
//
//         let best = null;
//
//         for (let t of ring) {
//             if (!canPlaceCastle(t.x, t.y, occupied, gridSize)) continue;
//
//             const compactness = adjacencyScore(t.x, t.y, occupied);
//
//             if (!best || compactness > best.compactness) {
//                 best = {x: t.x, y: t.y, compactness};
//             }
//         }
//
//         // if we found *any* valid spot at this distance, stop expanding
//         if (best) return best;
//     }
//
//     return null;
// }
//
// function findBestPlacement(castle, role, bears, occupied, gridSize) {
//     const target = getGravityTarget(role, bears);
//     const candidates = generateCandidates(target, occupied, gridSize);
//
//     if (!candidates.length) return null;
//
//     let best = null;
//     let bestScore = Infinity;
//
//     for (let t of candidates) {
//
//         // 🚫 HARD EXCLUSION: wrong bear zone
//         if (violatesOppositeBear(t.x, t.y, role, bears)) {
//             continue;
//         }
//
//         const score = placementScore(
//             t.x,
//             t.y,
//             castle,
//             role,
//             bears,
//             occupied,
//             gridSize
//         );
//
//
//         if (score < bestScore) {
//             bestScore = score;
//             best = t;
//         }
//     }
//
//     return best;
// }
//
// function adjacencyScore(x, y, occupied) {
//     let score = 0;
//
//     for (let dx = -1; dx <= 2; dx++) {
//         for (let dy = -1; dy <= 2; dy++) {
//             if (occupied.has(`${x + dx},${y + dy}`)) {
//                 score++;
//             }
//         }
//     }
//
//     return score;
// }
//
// function vacancyPenalty(x, y, occupied, gridSize) {
//     let penalty = 0;
//
//     // examine a 5x5 area around the 2x2 castle
//     for (let dx = -2; dx <= 3; dx++) {
//         for (let dy = -2; dy <= 3; dy++) {
//             const tx = x + dx;
//             const ty = y + dy;
//
//             if (
//                 tx < 0 || ty < 0 ||
//                 tx >= gridSize || ty >= gridSize
//             ) continue;
//
//             const key = `${tx},${ty}`;
//
//             // empty tile — check if it's becoming isolated
//             if (!occupied.has(key)) {
//                 let neighbors = 0;
//
//                 for (let nx = -1; nx <= 1; nx++) {
//                     for (let ny = -1; ny <= 1; ny++) {
//                         if (occupied.has(`${tx + nx},${ty + ny}`)) {
//                             neighbors++;
//                         }
//                     }
//                 }
//
//                 // isolated or thin corridor tile
//                 if (neighbors <= 1) penalty += 3;
//                 else if (neighbors === 2) penalty += 1;
//             }
//         }
//     }
//
//     return penalty;
// }
//
// function scorePlacement(x, y, bear, occupied, gridSize) {
//     const distance =
//         Math.abs(x - bear.x) + Math.abs(y - bear.y);
//
//     const vacancy = vacancyPenalty(x, y, occupied, gridSize);
//
//     const adjacency = adjacencyScore(x, y, occupied);
//
//     return {
//         distance,
//         vacancy,
//         adjacency,
//
//         // lower is better — vacancy DOMINATES
//         score:
//             vacancy * 1000 +       // 🚨 force density
//             distance * 10 -        // still prefers closer
//             adjacency * 2          // prefers snug
//     };
// }
//
// function validateCastles(castles) {
//     const missing = castles.filter(c =>
//         c.x == null || c.y == null || c.priority == null
//     );
//
//     if (missing.length) {
//         console.warn("Unplaced or invalid castles:", missing);
//         alert(`${missing.length} castles are not placed`);
//         return false;
//     }
//     return true;
// }
//
// function findAnyPlacement(occupied, gridSize) {
//     for (let x = 0; x < gridSize; x++) {
//         for (let y = 0; y < gridSize; y++) {
//             if (canPlaceCastle(x, y, occupied, gridSize)) {
//                 return {x, y};
//             }
//         }
//     }
//     return null;
// }
//
// function placementScore(x, y, castle, role, bears, occupied, gridSize) {
//     const p = castle.priority / 100;
//
//     const b1 = bears.find(b => b.id === "Bear 1");
//     const b2 = bears.find(b => b.id === "Bear 2");
//
//     let distance = 0;
//     let repulsion = 0;
//
//     if (role === "bear1") {
//         distance = Math.abs(x - b1.x) + Math.abs(y - b1.y);
//         repulsion = Math.max(0, 8 - (Math.abs(x - b2.x) + Math.abs(y - b2.y))) * 40;
//     }
//
//     if (role === "bear2") {
//         distance = Math.abs(x - b2.x) + Math.abs(y - b2.y);
//         repulsion = Math.max(0, 8 - (Math.abs(x - b1.x) + Math.abs(y - b1.y))) * 40;
//     }
//
//     if (role === "both") {
//         const mid = {
//             x: Math.round((b1.x + b2.x) / 2),
//             y: Math.round((b1.y + b2.y) / 2)
//         };
//         distance = Math.abs(x - mid.x) + Math.abs(y - mid.y);
//     }
//
//     const vacancy = vacancyPenalty(x, y, occupied, gridSize);
//     const adjacency = adjacencyScore(x, y, occupied);
//
//     return (
//         distance * (10 + p * 25) +   // priority-scaled gravity
//         vacancy * 1000 -             // compactness
//         adjacency * 5 +              // snugness
//         repulsion                    // wrong-bear push
//     );
// }
//
// function compactCastles(castles, bears, occupied, gridSize) {
//     // Pull castles inward to eliminate gaps
//     const center = gridSize / 2;
//
//     // sort by distance from cluster center (outermost first)
//     const sorted = castles
//         .filter(c => !c.locked)
//         .sort((a, b) => {
//             const da = Math.abs(a.x - center) + Math.abs(a.y - center);
//             const db = Math.abs(b.x - center) + Math.abs(b.y - center);
//             return db - da;
//         });
//
//     let moved = true;
//     let safety = 0;
//
//     while (moved && safety < 20) {
//         moved = false;
//         safety++;
//
//         for (let c of sorted) {
//             const original = {x: c.x, y: c.y};
//
//             // try 4-neighbour moves toward center
//             const candidates = [
//                 {x: c.x + Math.sign(center - c.x), y: c.y},
//                 {x: c.x, y: c.y + Math.sign(center - c.y)}
//             ];
//
//             for (let t of candidates) {
//                 // temporarily free current tiles
//                 for (let dx = 0; dx < 2; dx++) {
//                     for (let dy = 0; dy < 2; dy++) {
//                         occupied.delete(`${c.x + dx},${c.y + dy}`);
//                     }
//                 }
//
//                 if (canPlaceCastle(t.x, t.y, occupied, gridSize)) {
//                     c.x = t.x;
//                     c.y = t.y;
//                     occupyCastle(c.x, c.y, occupied);
//                     moved = true;
//                     break;
//                 }
//
//                 // restore original if failed
//                 occupyCastle(original.x, original.y, occupied);
//                 c.x = original.x;
//                 c.y = original.y;
//             }
//         }
//     }
// }
//
// function generateCandidates(target, occupied, gridSize, maxRadius = 12) {
//     const seen = new Set();
//     const candidates = [];
//
//     for (let r = 0; r <= maxRadius; r++) {
//         const ring = generateRingTiles(target.x, target.y, r, gridSize);
//
//         for (let t of ring) {
//             const key = `${t.x},${t.y}`;
//             if (seen.has(key)) continue;
//             seen.add(key);
//
//             if (canPlaceCastle(t.x, t.y, occupied, gridSize)) {
//                 candidates.push(t);
//             }
//         }
//     }
//
//     return candidates;
// }
//
// // ==========================
// // Mouse Helpers
// // ==========================
//
// // function onMouseDown(e) {
// //     if (!mapData) return;
// //     if (draggingCastle || draggingBear) return; // prevent re-entry
// //
// //     const rect = canvas.getBoundingClientRect();
// //     const {x, y} = screenToGrid(
// //         e.clientX - rect.left,
// //         e.clientY - rect.top
// //     );
// //
// //     // ---- CASTLES FIRST ----
// //     for (let castle of mapData.castles || []) {
// //         if (castle.x == null || castle.y == null) continue;
// //
// //         if (isPointInCastle(x, y, castle)) {
// //             if (castle.locked) return;
// //             if (window.remoteBusy?.has(castle.id)) return;
// //
// //             draggingCastle = castle;
// // Sync.markBusy(castle.id);
// // drawMap(mapData);
// //
// //
// //             castle._original = {x: castle.x, y: castle.y};
// //             castle._grab = {dx: x - castle.x, dy: y - castle.y};
// //             return;
// //         }
// //     }
// //
// //     // ---- THEN BEARS ----
// //     for (let bear of mapData.bear_traps || []) {
// //         if (
// //             x >= bear.x - 1 && x <= bear.x + 1 &&
// //             y >= bear.y - 1 && y <= bear.y + 1
// //         ) {
// //             if (bear.locked) return;
// //
// //            if (window.remoteBusy?.has(bear.id)) return;
// //
// // draggingBear = bear;
// // Sync.markBusy(bear.id);
// // drawMap(mapData);
// //
// // bear._original = {x: bear.x, y: bear.y};
// // return;
// //
// //         }
// //     }
// // }
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
// // function onMouseUp() {
// //   // ---- CASTLE DROP ----
// //   if (draggingCastle) {
// //     const c = draggingCastle;
// //     const movedId = c.id;
// //
// //     c.x = Math.round(c.x);
// //     c.y = Math.round(c.y);
// //
// //     const valid =
// //       isCastleInBounds(c, mapData.grid_size) &&
// //       !overlapsCastle(c, mapData.castles) &&
// //       !overlapsBannerCastle(c, mapData.banners) &&
// //       !overlapsBearCastle(c, mapData.bear_traps);
// //
// //     if (!valid) {
// //       c.x = c._original.x;
// //       c.y = c._original.y;
// //     }
// //
// //     delete c._original;
// //     delete c._grab;
// //     draggingCastle = null;
// //
// //     c.efficiency = calculateEfficiency(c, mapData.bear_traps);
// //
// //     drawMap(mapData);
// //     renderCastleTable();
// //
// //     Sync.scheduleUpdate({
// //       id: c.id,
// //       x: c.x,
// //       y: c.y,
// //       efficiency: c.efficiency
// //     });
// //
// //     Sync.unmarkBusy(movedId);
// //     autosaveCastle(c, ["x", "y", "efficiency"]);
// //     return;
// //   }
// //
// //   // ---- BEAR DROP ----
// //   if (draggingBear) {
// //     const b = draggingBear;
// //     const movedId = b.id;
// //
// //     b.x = Math.round(b.x);
// //     b.y = Math.round(b.y);
// //
// //     delete b._original;
// //     draggingBear = null;
// //
// //     drawMap(mapData);
// //
// //     Sync.scheduleUpdate({
// //       id: b.id,
// //       x: b.x,
// //       y: b.y
// //     });
// //
// //     Sync.unmarkBusy(movedId);
// // autosaveBear(b, ["x", "y"]);
// //     return;
// //   }
// // }
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
//
// document
//     .getElementById("downloadBtn")
//     .addEventListener("click", downloadMapImage);
//
// document.getElementById("autoPlaceBtn")
//     ?.addEventListener("click", autoPlaceCastles);
//
// document
//     .getElementById("uploadCsvBtn")
//     .addEventListener("click", () => {
//         document.getElementById("csvUpload").click();
//     });
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
// window.Sync = Sync;
