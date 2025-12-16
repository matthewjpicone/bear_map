// ==========================
// Authentication Module
// ==========================

const Auth = (() => {
  const TOKEN_KEY = 'bear_map_token';
  const USER_KEY = 'bear_map_user';

  // ---------- Storage ----------
  function getToken() {
    return localStorage.getItem(TOKEN_KEY);
  }

  function setToken(token) {
    localStorage.setItem(TOKEN_KEY, token);
  }

  function removeToken() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  }

  function getUser() {
    const userJson = localStorage.getItem(USER_KEY);
    return userJson ? JSON.parse(userJson) : null;
  }

  function setUser(user) {
    localStorage.setItem(USER_KEY, JSON.stringify(user));
  }

  // ---------- API Calls ----------
  async function login(username, password) {
    const formData = new FormData();
    formData.append('username', username);
    formData.append('password', password);

    const response = await fetch('/api/auth/login', {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Login failed');
    }

    const data = await response.json();
    setToken(data.access_token);

    // Fetch user info
    await fetchUserInfo();
    return data;
  }

  async function register(username, password, fullName) {
    const response = await fetch('/api/auth/register', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        username,
        password,
        full_name: fullName,
      }),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Registration failed');
    }

    return await response.json();
  }

  async function fetchUserInfo() {
    const token = getToken();
    if (!token) return null;

    const response = await fetch('/api/auth/me', {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });

    if (!response.ok) {
      removeToken();
      return null;
    }

    const user = await response.json();
    setUser(user);
    return user;
  }

  function logout() {
    removeToken();
    updateUI();
  }

  // ---------- UI Updates ----------
  function updateUI() {
    const user = getUser();
    const loggedInUser = document.getElementById('loggedInUser');
    const notLoggedIn = document.getElementById('notLoggedIn');
    const username = document.getElementById('username');

    if (user) {
      loggedInUser.style.display = 'inline';
      notLoggedIn.style.display = 'none';
      username.textContent = user.full_name || user.username;
    } else {
      loggedInUser.style.display = 'none';
      notLoggedIn.style.display = 'inline';
    }
  }

  // ---------- Modal Handlers ----------
  function showLoginModal() {
    document.getElementById('loginModal').style.display = 'block';
    document.getElementById('loginError').style.display = 'none';
  }

  function hideLoginModal() {
    document.getElementById('loginModal').style.display = 'none';
    document.getElementById('loginForm').reset();
  }

  function showRegisterModal() {
    document.getElementById('registerModal').style.display = 'block';
    document.getElementById('registerError').style.display = 'none';
    document.getElementById('registerSuccess').style.display = 'none';
  }

  function hideRegisterModal() {
    document.getElementById('registerModal').style.display = 'none';
    document.getElementById('registerForm').reset();
  }

  // ---------- Event Handlers ----------
  function setupEventListeners() {
    // Login button
    document.getElementById('loginBtn').addEventListener('click', (e) => {
      e.preventDefault();
      showLoginModal();
    });

    // Cancel login
    document.getElementById('cancelLogin').addEventListener('click', hideLoginModal);

    // Login form submit
    document.getElementById('loginForm').addEventListener('submit', async (e) => {
      e.preventDefault();
      const username = document.getElementById('loginUsername').value;
      const password = document.getElementById('loginPassword').value;
      const errorDiv = document.getElementById('loginError');

      try {
        await login(username, password);
        hideLoginModal();
        updateUI();
        showToast(`Welcome back, ${username}!`, 'success');
      } catch (error) {
        errorDiv.textContent = error.message;
        errorDiv.style.display = 'block';
      }
    });

    // Show register modal
    document.getElementById('showRegister').addEventListener('click', (e) => {
      e.preventDefault();
      hideLoginModal();
      showRegisterModal();
    });

    // Show login modal from register
    document.getElementById('showLogin').addEventListener('click', (e) => {
      e.preventDefault();
      hideRegisterModal();
      showLoginModal();
    });

    // Cancel register
    document.getElementById('cancelRegister').addEventListener('click', hideRegisterModal);

    // Register form submit
    document.getElementById('registerForm').addEventListener('submit', async (e) => {
      e.preventDefault();
      const username = document.getElementById('registerUsername').value;
      const password = document.getElementById('registerPassword').value;
      const fullName = document.getElementById('registerFullName').value;
      const errorDiv = document.getElementById('registerError');
      const successDiv = document.getElementById('registerSuccess');

      try {
        await register(username, password, fullName);
        successDiv.textContent = 'Registration successful! You can now login.';
        successDiv.style.display = 'block';
        errorDiv.style.display = 'none';
        
        // Auto-login after registration
        setTimeout(async () => {
          try {
            await login(username, password);
            hideRegisterModal();
            updateUI();
            showToast(`Welcome, ${username}!`, 'success');
          } catch (err) {
            console.error('Auto-login failed:', err);
          }
        }, 1000);
      } catch (error) {
        errorDiv.textContent = error.message;
        errorDiv.style.display = 'block';
        successDiv.style.display = 'none';
      }
    });

    // Logout button
    document.getElementById('logoutBtn').addEventListener('click', (e) => {
      e.preventDefault();
      logout();
      showToast('Logged out successfully', 'info');
    });
  }

  // ---------- Initialization ----------
  async function init() {
    // Check if user is already logged in
    const token = getToken();
    if (token) {
      await fetchUserInfo();
    }
    updateUI();
    setupEventListeners();
  }

  // ---------- Public API ----------
  return {
    init,
    getToken,
    getUser,
    login,
    logout,
    isAuthenticated: () => !!getToken(),
  };
})();

// Initialize auth when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => Auth.init());
} else {
  Auth.init();
}
