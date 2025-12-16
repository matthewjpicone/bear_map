// =========================
// Bear Planner – Client Sync
// =========================

const AUTO_SAVE_INTERVAL = 5000; // 5 seconds

const Sync = (() => {
  let socket = null;
  let started = false;

  const userId = crypto.randomUUID();
  let userName = null;
  let saveTimer = null;
  let pendingUpdates = [];

  const locallyBusyIds = new Set();

  // ---------- USERNAME ----------
  function getUserName() {
    if (!userName) {
      userName = localStorage.getItem("bearPlannerUsername");
      if (!userName) {
        userName = prompt("Please enter your name for the Bear Planner:") || "Anonymous";
        localStorage.setItem("bearPlannerUsername", userName);
      }
    }
    return userName;
  }

  // ---------- INIT ----------
  function init() {
    if (started) return;
    started = true;

    // Get username after page loads
    getUserName();

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
      updated_by: userId,
      updated_by_name: userName
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
      
      // Show toast for editing start
      if (msg.user_name && typeof window.Toast !== "undefined") {
        const entityName = getEntityName(msg.id);
        window.Toast.info(`${msg.user_name} is editing ${entityName}`);
      }
      
      redraw();
      return;
    }

    if (msg.type === "release" && msg.id) {
      updateRemoteBusy(msg.id, false);
      
      // Show toast for editing finish
      if (msg.user_name && typeof window.Toast !== "undefined") {
        const entityName = getEntityName(msg.id);
        window.Toast.info(`${msg.user_name} finished editing ${entityName}`);
      }
      
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

  // ---------- HELPERS ----------
  function getEntityName(id) {
    if (!window.mapData) return id;
    
    // Try to find castle
    const castle = window.mapData.castles?.find(c => c.id === id);
    if (castle) {
      return castle.player || castle.id;
    }
    
    // Try to find bear trap
    const bear = window.mapData.bear_traps?.find(b => b.id === id);
    if (bear) {
      return bear.id;
    }
    
    return id;
  }

  // ---------- LOCAL LOCKING ----------
  function markBusy(id) {
    if (!id) return;
    locallyBusyIds.add(id);

    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ 
        type: "busy", 
        id,
        user_name: userName
      }));
    }
  }

  function unmarkBusy(id) {
    if (!id) return;
    locallyBusyIds.delete(id);

    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ 
        type: "release", 
        id,
        user_name: userName
      }));
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
