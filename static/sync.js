/**
 * Bear Planner – Client Sync Module
 *
 * Manages WebSocket connections for real-time synchronization of entity
 * positions and states across multiple clients with optimistic updates
 * and soft-locking mechanism.
 *
 * @module Sync
 * @author Matthew Picone
 * @date 2025-12-17
 */

const AUTO_SAVE_INTERVAL = 5000; // 5 seconds

const Sync = (() => {
  let socket = null;
  let started = false;

  const userId = crypto.randomUUID();
  let saveTimer = null;
  let pendingUpdates = [];

  const locallyBusyIds = new Set();

  // ---------- INIT ----------
  function init() {
    if (started) return;
    started = true;

    connectWebSocket();

    // periodic autosave safety net
    setInterval(flushUpdates, AUTO_SAVE_INTERVAL);
  }

  // ---------- WEBSOCKET ----------
  function connectWebSocket() {
    const scheme = location.protocol === "https:" ? "wss" : "ws";
    socket = new WebSocket(`${scheme}://${location.host}/ws`);

    socket.onopen = () => {
      console.log("🟢 Sync connected");
    };

    socket.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        handleServerMessage(msg);
      } catch (e) {
        console.error("Bad WS message", e);
      }
    };

    socket.onclose = () => {
      console.warn("🔴 Sync disconnected, retrying...");
      setTimeout(connectWebSocket, 2000);
    };
  }

  // ---------- OUTGOING ----------
  function scheduleUpdate(update) {
    if (!update || !update.id) return;

    const stamped = {
      ...update,
      updated_at: Date.now(),
      updated_by: userId
    };

    // coalesce by id (last write wins)
    const idx = pendingUpdates.findIndex(u => u.id === stamped.id);
    if (idx >= 0) {
      pendingUpdates[idx] = { ...pendingUpdates[idx], ...stamped };
    } else {
      pendingUpdates.push(stamped);
    }

    if (saveTimer) clearTimeout(saveTimer);
    saveTimer = setTimeout(flushUpdates, 250);
  }

  function flushUpdates() {
    if (!socket || socket.readyState !== WebSocket.OPEN) return;
    if (pendingUpdates.length === 0) return;

    socket.send(JSON.stringify({
      type: "batch_update",
      updates: pendingUpdates
    }));

    pendingUpdates = [];
  }

  // ---------- INCOMING ----------
  function handleServerMessage(msg) {
    if (!msg || !msg.type) return;

    if (msg.type === "state_init") {
      if (typeof window.loadFullState === "function") {
        window.loadFullState(msg.state);
      }
      return;
    }

    if (msg.type === "updates" && Array.isArray(msg.updates)) {
      msg.updates.forEach(applyUpdate);
      return;
    }

    if (msg.type === "busy" && msg.id) {
      updateRemoteBusy(msg.id, true);
      redraw();
      // Note: No toast for busy events as they don't include user info
      // and are transient (user is just starting to edit)
      return;
    }

    if (msg.type === "release" && msg.id) {
      updateRemoteBusy(msg.id, false);
      redraw();
      return;
    }
  }

  function applyUpdate(update) {
    if (!update || !update.id) return;
    if (update.updated_by === userId) return;
    if (locallyBusyIds.has(update.id)) return;

    if (typeof window.applyRemoteUpdate === "function") {
      window.applyRemoteUpdate(update);
    }

    // Show toast notification for the update
    if (window.ToastManager && update.updated_by) {
      showUpdateToast(update);
    }
  }

  function showUpdateToast(update) {
    if (!update || !update.id) return;

    // Determine entity type from ID
    let entityType = "entity";
    if (update.id.startsWith("Castle")) {
      entityType = "castle";
    } else if (update.id.startsWith("Bear")) {
      entityType = "bear trap";
    } else if (update.id.startsWith("B")) {
      entityType = "banner";
    }

    // Detect what changed to show appropriate toast
    // Check if position changed (move)
    if (update.x !== undefined || update.y !== undefined) {
      window.ToastManager.showMove(update.id, entityType, update.updated_by);
    }
    // Check if lock changed
    else if (update.locked !== undefined) {
      window.ToastManager.showLock(update.id, entityType, update.locked, update.updated_by);
    }
    // Otherwise, it's a general edit
    else {
      window.ToastManager.showEdit(update.id, entityType, update.updated_by);
    }
  }

  // ---------- BUSY STATE ----------
  function updateRemoteBusy(id, busy) {
    const rb = window.remoteBusy;
    if (!rb) return;

    if (busy) {
      if (typeof rb.add === "function") rb.add(id);          // Set
      else if (typeof rb.set === "function") rb.set(id, true); // Map
    } else {
      if (typeof rb.delete === "function") rb.delete(id);    // Set or Map
    }
  }

  function redraw() {
    if (window.mapData && typeof window.drawMap === "function") {
      window.drawMap(window.mapData);
    }
  }

  // ---------- LOCAL LOCKING ----------
  function markBusy(id) {
    if (!id) return;
    locallyBusyIds.add(id);

    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ type: "busy", id }));
    }
  }

  function unmarkBusy(id) {
    if (!id) return;
    locallyBusyIds.delete(id);

    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ type: "release", id }));
    }
  }

  return {
    init,
    scheduleUpdate,
    markBusy,
    unmarkBusy
  };
})();

window.Sync = Sync;
