// =========================
// Toast Notification System
// =========================

const Toast = (() => {
  let container = null;
  let toastCounter = 0;

  // ---------- INIT ----------
  function init() {
    // Create toast container if it doesn't exist
    container = document.getElementById("toastContainer");
    if (!container) {
      container = document.createElement("div");
      container.id = "toastContainer";
      container.className = "toast-container";
      document.body.appendChild(container);
    }
  }

  // ---------- SHOW TOAST ----------
  function show(message, options = {}) {
    if (!container) init();

    const duration = options.duration || 4000; // 4 seconds default
    const type = options.type || "info"; // info, success, warning, error

    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    toast.setAttribute("role", "alert");
    toast.setAttribute("aria-live", "polite");

    const toastId = ++toastCounter;
    toast.dataset.toastId = toastId;

    // Add to container (newer toasts at the bottom)
    container.appendChild(toast);

    // Trigger animation by adding 'show' class after a brief delay
    setTimeout(() => {
      toast.classList.add("show");
    }, 10);

    // Auto-remove after duration
    setTimeout(() => {
      removeToast(toast);
    }, duration);

    return toastId;
  }

  // ---------- REMOVE TOAST ----------
  function removeToast(toast) {
    if (!toast || !toast.parentElement) return;

    toast.classList.remove("show");
    toast.classList.add("hide");

    // Wait for animation to complete before removing from DOM
    setTimeout(() => {
      if (toast.parentElement) {
        toast.parentElement.removeChild(toast);
      }
    }, 300);
  }

  // ---------- HELPER METHODS ----------
  function info(message, duration) {
    return show(message, { type: "info", duration });
  }

  function success(message, duration) {
    return show(message, { type: "success", duration });
  }

  function warning(message, duration) {
    return show(message, { type: "warning", duration });
  }

  function error(message, duration) {
    return show(message, { type: "error", duration });
  }

  return {
    init,
    show,
    info,
    success,
    warning,
    error
  };
})();

window.Toast = Toast;
