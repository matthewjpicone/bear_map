// =========================
// Toast Notification System
// =========================

const ToastManager = (() => {
  const TOAST_DURATION = 5000; // 5 seconds before auto-dismiss
  const FADE_DURATION = 300; // milliseconds for fade-out animation

  // Store mapping of user IDs to friendly names (if available)
  const userNames = new Map();

  /**
   * Initialize the toast system
   */
  function init() {
    // Ensure toast container exists
    if (!document.getElementById("toastContainer")) {
      const container = document.createElement("div");
      container.id = "toastContainer";
      container.setAttribute("aria-live", "polite");
      document.body.appendChild(container);
    }
  }

  /**
   * Get a user-friendly name for a user ID
   *
   * @param {string} userId - The user ID
   * @returns {string} A friendly name or shortened ID
   */
  function getUserName(userId) {
    if (userNames.has(userId)) {
      return userNames.get(userId);
    }
    // Return first 8 characters of UUID for brevity
    return userId ? `User ${userId.substring(0, 8)}` : "Unknown User";
  }

  /**
   * Set a friendly name for a user ID
   *
   * @param {string} userId - The user ID
   * @param {string} name - The friendly name
   */
  function setUserName(userId, name) {
    if (userId && name) {
      userNames.set(userId, name);
    }
  }

  /**
   * Show a toast notification
   *
   * @param {string} message - The main message to display
   * @param {string} userId - The ID of the user who triggered the action
   * @param {string} actionType - The type of action (e.g., 'moved', 'locked', 'edited')
   * @param {string} type - The type of toast ('info', 'success', 'error', 'warning')
   */
  function show(message, userId = null, actionType = null, type = 'info') {
    console.log("ToastManager.show called with:", message, userId, actionType, type);
    const container = document.getElementById("toastContainer");
    if (!container) {
      console.warn("Toast container not found");
      return;
    }

    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;

    // Build toast content
    let content = "";
    if (userId) {
      const userName = getUserName(userId);
      content += `<span class="toast-user">${escapeHtml(userName)}</span> `;
    }
    content += escapeHtml(message);
    if (actionType) {
      content += ` <span class="toast-action">(${escapeHtml(actionType)})</span>`;
    }

    toast.innerHTML = content;
    container.appendChild(toast);

    // Auto-dismiss after duration
    setTimeout(() => {
      dismissToast(toast);
    }, TOAST_DURATION);
  }

  /**
   * Dismiss a toast with fade-out animation
   *
   * @param {HTMLElement} toast - The toast element to dismiss
   */
  function dismissToast(toast) {
    if (!toast || !toast.parentElement) return;

    toast.classList.add("fade-out");
    setTimeout(() => {
      if (toast.parentElement) {
        toast.parentElement.removeChild(toast);
      }
    }, FADE_DURATION);
  }

  /**
   * Show a toast for an entity move
   *
   * @param {string} entityId - The entity ID
   * @param {string} entityType - The entity type ('castle', 'bear', 'banner')
   * @param {string} userId - The user who moved it
   */
  function showMove(entityId, entityType, userId) {
    show(`moved ${entityType} ${entityId}`, userId, "moved");
  }

  /**
   * Show a toast for a lock/unlock action
   *
   * @param {string} entityId - The entity ID
   * @param {string} entityType - The entity type ('castle', 'bear', 'banner')
   * @param {boolean} locked - Whether locked or unlocked
   * @param {string} userId - The user who performed the action
   */
  function showLock(entityId, entityType, locked, userId) {
    const action = locked ? "locked" : "unlocked";
    show(`${action} ${entityType} ${entityId}`, userId, action);
  }

  /**
   * Show a toast for an entity edit
   *
   * @param {string} entityId - The entity ID
   * @param {string} entityType - The entity type ('castle', 'bear', 'banner')
   * @param {string} userId - The user who edited it
   */
  function showEdit(entityId, entityType, userId) {
    show(`edited ${entityType} ${entityId}`, userId, "updated");
  }

  /**
   * Show a toast for busy/lock acquisition
   *
   * @param {string} entityId - The entity ID
   * @param {string} userId - The user who acquired the lock
   */
  function showBusy(entityId, userId) {
    show(`is editing ${entityId}`, userId, "editing");
  }

  /**
   * Escape HTML to prevent XSS
   *
   * @param {string} text - Text to escape
   * @returns {string} Escaped text
   */
  function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }

  return {
    init,
    show,
    showMove,
    showLock,
    showEdit,
    showBusy,
    setUserName,
    getUserName
  };
})();

// Initialize on load
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", ToastManager.init);
} else {
  ToastManager.init();
}

// Make available globally
window.ToastManager = ToastManager;
