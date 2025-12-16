// ==========================
// Authentication Module
// ==========================

let currentUser = null;

/**
 * Initialize authentication state on page load
 */
async function initAuth() {
  try {
    const response = await fetch('/auth/me', {
      credentials: 'include'
    });
    
    if (!response.ok) {
      console.error('Failed to fetch user info');
      showLoginButton();
      return;
    }
    
    const data = await response.json();
    
    if (data.authenticated && data.user) {
      currentUser = data.user;
      showUserInfo(currentUser);
    } else {
      currentUser = null;
      showLoginButton();
    }
  } catch (error) {
    console.error('Error initializing auth:', error);
    showLoginButton();
  }
}

/**
 * Display user information in the header
 */
function showUserInfo(user) {
  const userInfo = document.getElementById('userInfo');
  const loginBtn = document.getElementById('loginBtn');
  const userAvatar = document.getElementById('userAvatar');
  const userName = document.getElementById('userName');
  
  if (!userInfo || !loginBtn || !userAvatar || !userName) {
    console.error('User UI elements not found');
    return;
  }
  
  // Set user avatar
  if (user.avatar) {
    const avatarUrl = `https://cdn.discordapp.com/avatars/${user.id}/${user.avatar}.png?size=64`;
    userAvatar.src = avatarUrl;
  } else {
    // Use default Discord avatar
    const defaultAvatarIndex = parseInt(user.discriminator) % 5;
    userAvatar.src = `https://cdn.discordapp.com/embed/avatars/${defaultAvatarIndex}.png`;
  }
  
  // Set username
  const displayName = user.global_name || user.username;
  userName.textContent = displayName;
  
  // Show user info, hide login button
  userInfo.style.display = 'flex';
  loginBtn.style.display = 'none';
}

/**
 * Display login button
 */
function showLoginButton() {
  const userInfo = document.getElementById('userInfo');
  const loginBtn = document.getElementById('loginBtn');
  
  if (!userInfo || !loginBtn) {
    console.error('User UI elements not found');
    return;
  }
  
  userInfo.style.display = 'none';
  loginBtn.style.display = 'block';
}

/**
 * Handle login button click
 */
function handleLogin() {
  window.location.href = '/auth/login';
}

/**
 * Handle logout button click
 */
async function handleLogout() {
  try {
    const response = await fetch('/auth/logout', {
      method: 'POST',
      credentials: 'include'
    });
    
    if (response.ok) {
      currentUser = null;
      showLoginButton();
      console.log('Logged out successfully');
    } else {
      console.error('Logout failed');
    }
  } catch (error) {
    console.error('Error during logout:', error);
  }
}

/**
 * Get current authenticated user
 */
function getCurrentUser() {
  return currentUser;
}

// Initialize auth on page load
document.addEventListener('DOMContentLoaded', () => {
  initAuth();
  
  // Attach event listeners
  const loginBtn = document.getElementById('loginBtn');
  const logoutBtn = document.getElementById('logoutBtn');
  
  if (loginBtn) {
    loginBtn.addEventListener('click', handleLogin);
  }
  
  if (logoutBtn) {
    logoutBtn.addEventListener('click', handleLogout);
  }
});
