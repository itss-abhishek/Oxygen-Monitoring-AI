/**
 * static/js/app.js — OxySense Web Application Flow & Dashboard Controller
 */

document.addEventListener('DOMContentLoaded', () => {
  // Initialize Lucide Icons
  if (window.lucide) {
    lucide.createIcons();
  }

  // ═════════════════════════════════════════════════════════════════════════
  // STATE MANAGEMENT
  // ═════════════════════════════════════════════════════════════════════════
  let streamInterval = null;
  let isStreaming = true;
  let currentView = 'view-overview';
  let currentScreen = 'screen-splash';
  let currentUser = null;

  // Restore session from sessionStorage if available
  const storedUser = sessionStorage.getItem('oxysense_user');
  if (storedUser) {
    try {
      currentUser = JSON.parse(storedUser);
    } catch (e) {
      currentUser = null;
    }
  }

  // ═════════════════════════════════════════════════════════════════════════
  // 1. SCREEN ROUTER & NAVIGATION FLOW
  // ═════════════════════════════════════════════════════════════════════════
  const screens = document.querySelectorAll('.app-screen');

  function showScreen(screenId) {
    // Route Protection: Dashboard requires authentication
    if (screenId === 'screen-dashboard' && !currentUser) {
      showToast('⚠️ Please sign in to access the clinical dashboard');
      showScreen('screen-login');
      return;
    }

    currentScreen = screenId;

    screens.forEach(s => {
      s.classList.remove('active');
    });

    const target = document.getElementById(screenId);
    if (target) {
      target.classList.add('active');
    }

    // Update screen-specific states
    if (screenId === 'screen-home') {
      updateHomeAuthState();
      OxyCharts.initHomePreviewChart();
      window.scrollTo(0, 0);
    } else if (screenId === 'screen-dashboard') {
      updateDashboardUserProfile();
      OxyCharts.initOverviewCharts();
      window.scrollTo(0, 0);
    } else if (screenId === 'screen-login') {
      const errBanner = document.getElementById('login-error-banner');
      if (errBanner) errBanner.style.display = 'none';
      window.scrollTo(0, 0);
    }

    if (window.lucide) lucide.createIcons();
  }

  function updateHomeAuthState() {
    const navAuthBtn = document.getElementById('btn-nav-auth');
    const navAuthText = document.getElementById('nav-auth-text');
    const heroCtaText = document.getElementById('hero-cta-text');

    if (currentUser) {
      if (navAuthText) navAuthText.textContent = 'Open Dashboard';
      if (navAuthBtn) {
        navAuthBtn.innerHTML = '<i data-lucide="layout-dashboard"></i> <span>Open Dashboard</span>';
      }
      if (heroCtaText) heroCtaText.textContent = 'Open Clinical Dashboard';
    } else {
      if (navAuthText) navAuthText.textContent = 'Login';
      if (navAuthBtn) {
        navAuthBtn.innerHTML = '<i data-lucide="log-in"></i> <span>Login</span>';
      }
      if (heroCtaText) heroCtaText.textContent = 'Explore Dashboard';
    }
    if (window.lucide) lucide.createIcons();
  }

  function updateDashboardUserProfile() {
    if (!currentUser) return;
    const nameEl = document.getElementById('dash-user-name');
    const roleEl = document.getElementById('dash-user-role');
    const avatarEl = document.getElementById('dash-user-avatar');

    if (nameEl) nameEl.textContent = currentUser.name || currentUser.full_name || 'Staff User';
    if (roleEl) roleEl.textContent = currentUser.role || 'Clinical Operator';
    if (avatarEl) {
      const initials = (currentUser.name || currentUser.full_name || 'SU')
        .split(' ')
        .map(n => n[0])
        .join('')
        .substring(0, 2)
        .toUpperCase();
      avatarEl.textContent = initials;
    }

    // Role-based visibility and action controls
    const navUsers = document.getElementById('nav-item-users');
    const isAdmin = Boolean(currentUser && (currentUser.role === 'ADMIN' || currentUser.role === 'MAIN_ADMIN' || currentUser.is_main_admin));

    if (navUsers) {
      navUsers.style.display = isAdmin ? 'flex' : 'none';
    }

    // Restrict simulation buttons & operational settings for Viewers
    const simBtns = document.querySelectorAll('#btn-sim-low, #btn-sim-leak, #btn-sim-reset, #btn-save-settings');
    simBtns.forEach(b => {
      if (!isAdmin) {
        b.disabled = true;
        b.style.opacity = '0.45';
        b.style.cursor = 'not-allowed';
        b.title = 'Viewer Mode: Administrative permissions required';
      } else {
        b.disabled = false;
        b.style.opacity = '1';
        b.style.cursor = 'pointer';
        b.removeAttribute('title');
      }
    });

    // If a Viewer navigated to view-users, redirect to view-overview
    if (!isAdmin && currentView === 'view-users') {
      switchView('view-overview');
    }
  }

  // ═════════════════════════════════════════════════════════════════════════
  // 2. SPLASH SCREEN INITIALIZATION
  // ═════════════════════════════════════════════════════════════════════════
  function initSplashScreen() {
    const progressBar = document.getElementById('splash-progress');
    const statusText = document.getElementById('splash-status');
    const splashScreen = document.getElementById('screen-splash');

    let progress = 15;
    if (progressBar) progressBar.style.width = '15%';

    const splashTimer = setInterval(() => {
      progress += 25;
      if (progressBar) progressBar.style.width = `${progress}%`;

      if (progress === 40 && statusText) {
        statusText.textContent = 'Loading IoT telemetry models...';
      } else if (progress === 65 && statusText) {
        statusText.textContent = 'Synchronizing simulation engine...';
      } else if (progress >= 100) {
        clearInterval(splashTimer);
        if (statusText) statusText.textContent = 'System ready.';

        setTimeout(() => {
          splashScreen?.classList.add('fade-out');
          setTimeout(() => {
            splashScreen?.classList.remove('active');
            splashScreen?.classList.remove('fade-out');

            // Default to Home Page; if user is already logged in on refresh, go to Dashboard
            if (currentUser) {
              showScreen('screen-dashboard');
              showToast(`Welcome back, ${currentUser.name}`);
            } else {
              showScreen('screen-home');
            }
          }, 350);
        }, 300);
      }
    }, 180);
  }

  // ═════════════════════════════════════════════════════════════════════════
  // 3. HOME PAGE INTERACTIONS
  // ═════════════════════════════════════════════════════════════════════════
  // Navbar Login / Dashboard CTA
  document.getElementById('btn-nav-auth')?.addEventListener('click', () => {
    if (currentUser) {
      showScreen('screen-dashboard');
    } else {
      showScreen('screen-login');
    }
  });

  // Hero Explore Dashboard CTA
  document.getElementById('btn-hero-dashboard')?.addEventListener('click', () => {
    if (currentUser) {
      showScreen('screen-dashboard');
    } else {
      showScreen('screen-login');
    }
  });

  // Preview Card Launch CTA
  document.getElementById('btn-preview-launch')?.addEventListener('click', () => {
    if (currentUser) {
      showScreen('screen-dashboard');
    } else {
      showScreen('screen-login');
    }
  });

  // Footer Login button
  document.getElementById('btn-footer-login')?.addEventListener('click', () => {
    showScreen('screen-login');
  });

  // Smooth scroll for Home nav links with sticky header offset
  document.querySelectorAll('.home-nav-link').forEach(link => {
    link.addEventListener('click', (e) => {
      const targetId = link.getAttribute('href');
      if (targetId && targetId.startsWith('#')) {
        e.preventDefault();
        document.querySelectorAll('.home-nav-link').forEach(l => l.classList.remove('active'));
        link.classList.add('active');

        if (targetId === '#screen-home') {
          window.scrollTo({ top: 0, behavior: 'smooth' });
        } else {
          const section = document.querySelector(targetId);
          if (section) {
            const navHeight = 72;
            const topPos = section.getBoundingClientRect().top + window.pageYOffset - navHeight;
            window.scrollTo({ top: topPos, behavior: 'smooth' });
          }
        }
      }
    });
  });

  // ScrollSpy: dynamically highlight navbar link matching current section in view
  const navSpyTargets = [
    { id: 'screen-home', link: document.querySelector('.home-nav-link[href="#screen-home"]') },
    { id: 'home-features', link: document.querySelector('.home-nav-link[href="#home-features"]') },
    { id: 'home-how', link: document.querySelector('.home-nav-link[href="#home-how"]') },
    { id: 'home-preview', link: document.querySelector('.home-nav-link[href="#home-preview"]') },
    { id: 'home-about', link: document.querySelector('.home-nav-link[href="#home-about"]') }
  ];

  function updateScrollSpy() {
    const homeScreen = document.getElementById('screen-home');
    if (!homeScreen || !homeScreen.classList.contains('active')) return;

    const scrollY = window.pageYOffset || document.documentElement.scrollTop;
    const navOffset = 140;
    let activeId = 'screen-home';

    if ((window.innerHeight + scrollY) >= (document.body.offsetHeight - 80)) {
      activeId = 'home-about';
    } else {
      navSpyTargets.forEach(({ id }) => {
        const el = document.getElementById(id);
        if (el) {
          const top = el.offsetTop - navOffset;
          if (scrollY >= top) {
            activeId = id;
          }
        }
      });
    }

    navSpyTargets.forEach(({ id, link }) => {
      if (link) {
        if (id === activeId) {
          link.classList.add('active');
        } else {
          link.classList.remove('active');
        }
      }
    });
  }

  // Scroll To Top Floating Button & ScrollSpy listener
  const scrollTopBtn = document.getElementById('btn-scroll-top');
  window.addEventListener('scroll', () => {
    const homeScreen = document.getElementById('screen-home');
    if (homeScreen && homeScreen.classList.contains('active')) {
      if (window.scrollY > 280) {
        scrollTopBtn?.classList.add('visible');
      } else {
        scrollTopBtn?.classList.remove('visible');
      }
      updateScrollSpy();
    } else {
      scrollTopBtn?.classList.remove('visible');
    }
  }, { passive: true });

  scrollTopBtn?.addEventListener('click', () => {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  });

  // ═════════════════════════════════════════════════════════════════════════
  // 4. LOGIN PAGE & AUTHENTICATION
  // ═════════════════════════════════════════════════════════════════════════
  const loginForm = document.getElementById('form-login');
  const registerForm = document.getElementById('form-register');
  const loginEmailInput = document.getElementById('input-login-email');
  const loginPwdInput = document.getElementById('input-login-password');
  const pwdToggleBtn = document.getElementById('btn-toggle-pwd');
  const pwdEyeIcon = document.getElementById('icon-pwd-eye');
  const loginErrorBanner = document.getElementById('login-error-banner');
  const loginErrorText = document.getElementById('login-error-text');
  const loginSubmitBtn = document.getElementById('btn-login-submit');
  const loginBtnText = document.getElementById('login-btn-text');
  const loginSpinner = document.getElementById('login-spinner');

  // Registration Elements
  const tabBtnSignIn = document.getElementById('tab-btn-signin');
  const tabBtnRegister = document.getElementById('tab-btn-register');
  const regStep1 = document.getElementById('register-step-1');
  const regStep2 = document.getElementById('register-step-2');
  const regNameInput = document.getElementById('input-reg-name');
  const regEmailInput = document.getElementById('input-reg-email');
  const regOtpInput = document.getElementById('input-reg-otp');
  const regPwdInput = document.getElementById('input-reg-password');
  const btnSendOtp = document.getElementById('btn-send-otp');
  const sendOtpBtnText = document.getElementById('send-otp-btn-text');
  const sendOtpSpinner = document.getElementById('send-otp-spinner');
  const btnVerifySubmit = document.getElementById('btn-verify-submit');
  const verifyBtnText = document.getElementById('verify-btn-text');
  const verifySpinner = document.getElementById('verify-spinner');
  const btnBackToStep1 = document.getElementById('btn-back-to-step1');

  // Auth Mode Tabs switching
  tabBtnSignIn?.addEventListener('click', () => {
    tabBtnSignIn.classList.add('active');
    tabBtnRegister.classList.remove('active');
    loginForm.style.display = 'block';
    registerForm.style.display = 'none';
    if (loginErrorBanner) loginErrorBanner.style.display = 'none';
  });

  tabBtnRegister?.addEventListener('click', () => {
    tabBtnRegister.classList.add('active');
    tabBtnSignIn.classList.remove('active');
    loginForm.style.display = 'none';
    registerForm.style.display = 'block';
    regStep1.style.display = 'block';
    regStep2.style.display = 'none';
    if (loginErrorBanner) loginErrorBanner.style.display = 'none';
  });

  // Step 1: Send OTP
  btnSendOtp?.addEventListener('click', async () => {
    const email = regEmailInput.value.trim().toLowerCase();
    const name = regNameInput.value.trim();

    if (!email || !name) {
      if (loginErrorText) loginErrorText.textContent = 'Please enter both your full name and @iilm.edu email.';
      if (loginErrorBanner) loginErrorBanner.style.display = 'flex';
      return;
    }

    if (!email.endsWith('@iilm.edu')) {
      if (loginErrorText) loginErrorText.textContent = 'Registration rejected: Only institutional emails ending with @iilm.edu are permitted.';
      if (loginErrorBanner) loginErrorBanner.style.display = 'flex';
      return;
    }

    btnSendOtp.disabled = true;
    sendOtpBtnText.style.display = 'none';
    sendOtpSpinner.style.display = 'inline-block';
    if (loginErrorBanner) loginErrorBanner.style.display = 'none';

    try {
      const res = await OxyAPI.requestRegistrationOtp(email, name);
      if (res.success) {
        showToast(res.message);
        regStep1.style.display = 'none';
        regStep2.style.display = 'block';
        const bannerText = document.getElementById('reg-step2-banner-text');
        if (res.dev_otp) {
          regOtpInput.value = res.dev_otp;
          if (bannerText) {
            bannerText.innerHTML = `Dev Mode (SMTP Offline): Your OTP is <strong>${res.dev_otp}</strong> (auto-filled below).`;
          }
        } else if (bannerText) {
          bannerText.textContent = `Verification OTP dispatched to ${email}. Code expires in 10 minutes.`;
        }
        regOtpInput.focus();
      } else {
        if (loginErrorText) loginErrorText.textContent = res.error || 'Failed to dispatch verification code.';
        if (loginErrorBanner) loginErrorBanner.style.display = 'flex';
      }
    } catch (err) {
      if (loginErrorText) loginErrorText.textContent = 'Cannot connect to backend server. Ensure python server.py is running.';
      if (loginErrorBanner) loginErrorBanner.style.display = 'flex';
    } finally {
      btnSendOtp.disabled = false;
      sendOtpBtnText.style.display = 'inline';
      sendOtpSpinner.style.display = 'none';
    }
  });

  // Step 2: Back to Step 1
  btnBackToStep1?.addEventListener('click', () => {
    regStep2.style.display = 'none';
    regStep1.style.display = 'block';
    if (loginErrorBanner) loginErrorBanner.style.display = 'none';
  });

  // Step 2: Verify OTP and Register
  registerForm?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const email = regEmailInput.value.trim().toLowerCase();
    const name = regNameInput.value.trim();
    const otp = regOtpInput.value.trim();
    const password = regPwdInput.value;

    if (!otp || otp.length !== 6) {
      if (loginErrorText) loginErrorText.textContent = 'Please enter the 6-digit verification code.';
      if (loginErrorBanner) loginErrorBanner.style.display = 'flex';
      return;
    }

    if (!password || password.length < 8) {
      if (loginErrorText) loginErrorText.textContent = 'Password must be at least 8 characters long.';
      if (loginErrorBanner) loginErrorBanner.style.display = 'flex';
      return;
    }

    btnVerifySubmit.disabled = true;
    verifyBtnText.style.display = 'none';
    verifySpinner.style.display = 'inline-block';
    if (loginErrorBanner) loginErrorBanner.style.display = 'none';

    try {
      const res = await OxyAPI.verifyRegistrationOtp(email, otp, password, name);
      if (res.success && res.user) {
        currentUser = res.user;
        sessionStorage.setItem('oxysense_user', JSON.stringify(res.user));
        showToast('Registration complete! Welcome to OxySense (Viewer Role assigned).');
        showScreen('screen-dashboard');
      } else {
        if (loginErrorText) loginErrorText.textContent = res.error || 'Verification failed.';
        if (loginErrorBanner) loginErrorBanner.style.display = 'flex';
      }
    } catch (err) {
      if (loginErrorText) loginErrorText.textContent = 'Cannot connect to backend server. Ensure python server.py is running.';
      if (loginErrorBanner) loginErrorBanner.style.display = 'flex';
    } finally {
      btnVerifySubmit.disabled = false;
      verifyBtnText.style.display = 'inline';
      verifySpinner.style.display = 'none';
    }
  });

  // Back to Home
  document.getElementById('btn-login-back')?.addEventListener('click', () => {
    showScreen('screen-home');
  });

  // Show/Hide password toggle
  pwdToggleBtn?.addEventListener('click', () => {
    if (loginPwdInput.type === 'password') {
      loginPwdInput.type = 'text';
      pwdEyeIcon?.setAttribute('data-lucide', 'eye-off');
    } else {
      loginPwdInput.type = 'password';
      pwdEyeIcon?.setAttribute('data-lucide', 'eye');
    }
    if (window.lucide) lucide.createIcons();
  });

  // Login form submission
  loginForm?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const email = loginEmailInput.value.trim();
    const password = loginPwdInput.value;

    if (!email || !password) {
      if (loginErrorText) loginErrorText.textContent = 'Please enter both email and password.';
      if (loginErrorBanner) loginErrorBanner.style.display = 'flex';
      return;
    }

    // Set loading state
    if (loginSubmitBtn) loginSubmitBtn.disabled = true;
    if (loginBtnText) loginBtnText.style.display = 'none';
    if (loginSpinner) loginSpinner.style.display = 'inline-block';
    if (loginErrorBanner) loginErrorBanner.style.display = 'none';

    try {
      const res = await OxyAPI.login(email, password);
      if (res.success && res.user) {
        currentUser = res.user;
        sessionStorage.setItem('oxysense_user', JSON.stringify(res.user));
        showToast(`Signed in successfully as ${res.user.name || res.user.full_name}`);
        showScreen('screen-dashboard');
      } else {
        if (loginErrorText) loginErrorText.textContent = res.error || 'Invalid credentials. Use @iilm.edu credentials.';
        if (loginErrorBanner) loginErrorBanner.style.display = 'flex';
      }
    } catch (err) {
      if (loginErrorText) loginErrorText.textContent = 'Connection error. Ensure the server is running.';
      if (loginErrorBanner) loginErrorBanner.style.display = 'flex';
    } finally {
      if (loginSubmitBtn) loginSubmitBtn.disabled = false;
      if (loginBtnText) loginBtnText.style.display = 'inline';
      if (loginSpinner) loginSpinner.style.display = 'none';
    }
  });

  // ═════════════════════════════════════════════════════════════════════════
  // 5. DASHBOARD HEADER ACTIONS (Home & Logout)
  // ═════════════════════════════════════════════════════════════════════════
  // Navigate back to Home page
  document.getElementById('btn-dash-home')?.addEventListener('click', () => {
    showScreen('screen-home');
  });

  // Logout action
  document.getElementById('btn-dash-logout')?.addEventListener('click', async () => {
    try {
      await OxyAPI.logout();
    } catch (e) {
      // Ignore network errors on logout
    }
    currentUser = null;
    sessionStorage.removeItem('oxysense_user');
    showToast('Logged out successfully.');
    showScreen('screen-home');
  });

  // ═════════════════════════════════════════════════════════════════════════
  // 6. DASHBOARD INTERNAL VIEW SWITCHING (Overview, Live, Fleet, etc.)
  // ═════════════════════════════════════════════════════════════════════════
  const navItems = document.querySelectorAll('.sidebar-menu .nav-item');
  const pageViews = document.querySelectorAll('.page-view');

  function switchView(viewId) {
    currentView = viewId;
    navItems.forEach(item => {
      if (item.getAttribute('data-view') === viewId) {
        item.classList.add('active');
      } else {
        item.classList.remove('active');
      }
    });

    pageViews.forEach(view => {
      if (view.id === viewId) {
        view.classList.add('active');
      } else {
        view.classList.remove('active');
      }
    });

    // View-specific initializers
    if (viewId === 'view-overview') {
      OxyCharts.initOverviewCharts();
      loadAiInsights();
    } else if (viewId === 'view-live') {
      OxyCharts.initLiveFullChart();
    } else if (viewId === 'view-cylinders') {
      loadCylinderFleet();
    } else if (viewId === 'view-alerts') {
      loadAlertsView();
    } else if (viewId === 'view-ai') {
      loadAiInsights();
    } else if (viewId === 'view-history') {
      loadHistoryTable();
    } else if (viewId === 'view-settings') {
      loadSettingsForm();
    } else if (viewId === 'view-users') {
      loadAdminUsers();
    }

    if (window.lucide) lucide.createIcons();
  }

  function closeMobileSidebar() {
    document.getElementById('sidebar')?.classList.remove('mobile-open');
    document.getElementById('sidebar-overlay')?.classList.remove('active');
  }

  function toggleMobileSidebar() {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebar-overlay');
    const isOpen = sidebar?.classList.toggle('mobile-open');
    overlay?.classList.toggle('active', !!isOpen);
  }

  navItems.forEach(item => {
    item.addEventListener('click', () => {
      const targetView = item.getAttribute('data-view');
      switchView(targetView);
      closeMobileSidebar();
    });
  });

  // Mobile menu toggle & close handlers
  document.getElementById('mobile-menu-btn')?.addEventListener('click', toggleMobileSidebar);
  document.getElementById('sidebar-close-btn')?.addEventListener('click', closeMobileSidebar);
  document.getElementById('sidebar-overlay')?.addEventListener('click', closeMobileSidebar);

  // Quick jump button from overview to fleet
  document.getElementById('btn-view-all-cylinders')?.addEventListener('click', () => {
    switchView('view-cylinders');
  });

  // Header notif icon jump to alerts
  document.getElementById('header-notif-btn')?.addEventListener('click', () => {
    switchView('view-alerts');
  });

  // ═════════════════════════════════════════════════════════════════════════
  // UI-STYLING: THEME MANAGEMENT (Light / Dark Mode with Persistence)
  // ═════════════════════════════════════════════════════════════════════════
  function initTheme() {
    const savedTheme = localStorage.getItem('oxysense-theme') || 
      (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
    applyTheme(savedTheme);
  }

  function applyTheme(theme) {
    if (theme === 'dark') {
      document.documentElement.classList.add('dark');
      document.body.classList.remove('theme-light');
      document.body.classList.add('theme-dark');
      localStorage.setItem('oxysense-theme', 'dark');
    } else {
      document.documentElement.classList.remove('dark');
      document.body.classList.remove('theme-dark');
      document.body.classList.add('theme-light');
      localStorage.setItem('oxysense-theme', 'light');
    }
    if (window.lucide) lucide.createIcons();
    if (window.OxyCharts && typeof OxyCharts.updateTheme === 'function') {
      OxyCharts.updateTheme(theme);
    }
  }

  function toggleTheme() {
    const isDark = document.documentElement.classList.contains('dark');
    applyTheme(isDark ? 'light' : 'dark');
  }

  document.getElementById('theme-toggle-btn')?.addEventListener('click', toggleTheme);
  document.getElementById('home-theme-toggle')?.addEventListener('click', toggleTheme);
  initTheme();

  // ═════════════════════════════════════════════════════════════════════════
  // 7. TELEMETRY POLLING & LIVE STREAM
  // ═════════════════════════════════════════════════════════════════════════
  async function pollLiveTelemetry() {
    try {
      const data = await OxyAPI.getLiveStream();
      renderOverviewMetrics(data);
      OxyCharts.updateFromHistory(data.history, currentPrescribedFlow);

      // Also update home page preview card if visible
      const homeP = document.getElementById('home-preview-p');
      const homePSub = document.getElementById('home-preview-p-sub');
      const homeF = document.getElementById('home-preview-f');
      if (homeP) homeP.innerHTML = `${data.pressure.psi} <small>PSI</small>`;
      if (homePSub) homePSub.textContent = `${data.pressure.bar} bar · ${data.pressure.percentage}% Capacity`;
      if (homeF) homeF.innerHTML = `${data.flow.value.toFixed(1)} <small>L/min</small>`;

      // Refresh tables if currently visible
      if (currentScreen === 'screen-dashboard') {
        if (currentView === 'view-cylinders') {
          loadCylinderFleet(false);
        }
      }
    } catch (err) {
      console.error('Telemetry polling error:', err);
    }
  }

  function startStreaming() {
    if (streamInterval) clearInterval(streamInterval);
    pollLiveTelemetry();
    streamInterval = setInterval(pollLiveTelemetry, 2000);
    isStreaming = true;
    updateStreamButtonState();
  }

  function stopStreaming() {
    if (streamInterval) {
      clearInterval(streamInterval);
      streamInterval = null;
    }
    isStreaming = false;
    updateStreamButtonState();
  }

  function updateStreamButtonState() {
    const btn = document.getElementById('btn-toggle-stream');
    if (!btn) return;
    if (isStreaming) {
      btn.innerHTML = '<i data-lucide="pause"></i> Pause Stream';
      btn.className = 'btn btn-primary';
    } else {
      btn.innerHTML = '<i data-lucide="play"></i> Resume Stream';
      btn.className = 'btn btn-warning-soft';
    }
    if (window.lucide) lucide.createIcons();
  }

  document.getElementById('btn-toggle-stream')?.addEventListener('click', () => {
    if (isStreaming) {
      stopStreaming();
      showToast('Live telemetry stream paused');
    } else {
      startStreaming();
      showToast('Live telemetry stream resumed');
    }
  });

  // ═════════════════════════════════════════════════════════════════════════
  // 8. DASHBOARD OVERVIEW METRICS RENDERING
  // ═════════════════════════════════════════════════════════════════════════
  let activeCylinderId = 'CYL-ICU-101';
  let currentPrescribedFlow = 2.0;

  async function changeActiveCylinder(newCylId) {
    if (!newCylId) return;
    try {
      const res = await OxyAPI.setActiveCylinder(newCylId);
      if (res.success) {
        activeCylinderId = res.active_cylinder_id;

        // Synchronize all cylinder selector dropdowns
        const selectEl = document.getElementById('select-active-cylinder');
        if (selectEl) selectEl.value = activeCylinderId;

        const globalSelect = document.getElementById('global-select-cylinder');
        if (globalSelect) globalSelect.value = activeCylinderId;

        const historySelect = document.getElementById('history-select-cylinder');
        if (historySelect) historySelect.value = activeCylinderId;

        const histTag = document.getElementById('history-active-cyl-tag');
        if (histTag) histTag.textContent = `Monitoring: ${activeCylinderId}`;

        const csvBtn = document.getElementById('btn-export-csv');
        if (csvBtn) {
          csvBtn.href = `/api/export-csv?cylinder_id=${encodeURIComponent(activeCylinderId)}`;
          csvBtn.setAttribute('download', `oxysense_${activeCylinderId.toLowerCase()}_report.csv`);
        }

        document.querySelectorAll('.btn-cyl-pill').forEach(btn => {
          if (btn.getAttribute('data-cyl') === activeCylinderId) {
            btn.classList.add('active');
          } else {
            btn.classList.remove('active');
          }
        });

        await pollLiveTelemetry();

        // Refresh AI operational insights for the newly selected cylinder
        loadAiInsights();

        // If currently in Historical Reports view, refresh the table
        if (currentView === 'view-history') {
          await loadHistoryTable();
        }

        showToast(`Monitoring active cylinder: ${activeCylinderId}`);
      } else {
        showToast(`Failed to switch cylinder: ${res.error || 'Unknown error'}`);
      }
    } catch (err) {
      console.error('Error switching active cylinder:', err);
    }
  }

  // Bind dropdown change handlers
  document.getElementById('select-active-cylinder')?.addEventListener('change', (e) => {
    changeActiveCylinder(e.target.value);
  });

  document.getElementById('history-select-cylinder')?.addEventListener('change', (e) => {
    changeActiveCylinder(e.target.value);
  });

  // Bind quick pills click
  document.querySelectorAll('.btn-cyl-pill').forEach(btn => {
    btn.addEventListener('click', () => {
      const cyl = btn.getAttribute('data-cyl');
      changeActiveCylinder(cyl);
    });
  });

  function renderOverviewMetrics(data) {
    if (!data) return;

    // Active Cylinder Selector Bar sync
    const cylTitle = document.getElementById('active-cyl-title');
    const cylBadge = document.getElementById('active-cyl-status-badge');
    const assignedWard = document.getElementById('val-assigned-ward');
    const selectEl = document.getElementById('select-active-cylinder');

    if (cylTitle && data.device) {
      cylTitle.textContent = `${data.device.id} — ${data.device.ward}`;
    }
    if (assignedWard && data.device) {
      assignedWard.textContent = `Assigned: ${data.device.ward}`;
    }
    if (cylBadge && data.status) {
      if (!data.device.esp32_connected) {
        cylBadge.textContent = 'DISCONNECTED';
        cylBadge.className = 'status-pill-large badge-disconnected';
      } else {
        cylBadge.textContent = data.status.label;
        cylBadge.className = `status-pill-large ${data.status.badge_class}`;
      }
    }

    const cylPulse = document.getElementById('active-cyl-pulse');
    if (cylPulse) {
      if (data.device.esp32_connected) {
        cylPulse.className = 'live-dot-pulse text-xs';
        cylPulse.textContent = '● Live Telemetry';
      } else {
        cylPulse.className = 'text-xs text-rose-500 font-bold';
        cylPulse.textContent = '○ Hardware Stopped';
      }
    }
    if (selectEl && data.device && selectEl.value !== data.device.id) {
      selectEl.value = data.device.id;
    }
    document.querySelectorAll('.btn-cyl-pill').forEach(btn => {
      if (btn.getAttribute('data-cyl') === data.device.id) {
        btn.classList.add('active');
      } else {
        btn.classList.remove('active');
      }
    });

    // Clock & Connection
    const clockEl = document.getElementById('live-clock');
    if (clockEl) clockEl.textContent = data.device.last_update || '--:--:--';

    const pill = document.getElementById('esp32-status-pill');
    const pillText = document.getElementById('esp32-status-text');
    if (pill && pillText) {
      if (data.device.esp32_connected) {
        pill.className = 'status-pill online';
        pillText.textContent = data.device.data_source?.includes('HARDWARE') ? 'ESP32 Hardware Online' : 'ESP32 Connected (Simulated)';
      } else if (data.hardware_bridge && data.hardware_bridge.status === 'busy') {
        pill.className = 'status-pill warning';
        pillText.textContent = `${data.hardware_bridge.detected_port} Busy: Close Arduino Serial Monitor`;
      } else {
        pill.className = 'status-pill offline';
        pillText.textContent = 'ESP32 Disconnected (Offline)';
      }
    }

    const demoBadge = document.querySelector('.demo-badge');
    if (demoBadge) {
      if (data.hardware_bridge && data.hardware_bridge.status === 'busy') {
        demoBadge.className = 'demo-badge bg-amber-500/20 text-amber-400 border border-amber-500/30';
        demoBadge.innerHTML = '<i data-lucide="alert-triangle" class="icon-sm"></i> <span>PORT BUSY (CLOSE ARDUINO IDE)</span>';
      } else if (!data.device.esp32_connected) {
        demoBadge.className = 'demo-badge bg-rose-500/20 text-rose-500 border border-rose-500/30';
        demoBadge.innerHTML = '<i data-lucide="wifi-off" class="icon-sm"></i> <span>ESP32 DISCONNECTED</span>';
      } else if (data.device.data_source?.includes('HARDWARE')) {
        demoBadge.className = 'demo-badge bg-emerald-500/20 text-emerald-500 border border-emerald-500/30';
        demoBadge.innerHTML = '<i data-lucide="cpu" class="icon-sm"></i> <span>HARDWARE LIVE</span>';
      } else {
        demoBadge.className = 'demo-badge';
        demoBadge.innerHTML = '<i data-lucide="flask-conical" class="icon-sm"></i> <span>DEMO MODE</span>';
      }
    }

    // Card A: Pressure
    const pVal = Math.max(0, data.pressure.value || 0);
    const pUnit = data.pressure.unit;
    const pPri = document.getElementById('val-pressure-primary');
    const pUnitEl = document.getElementById('unit-pressure-primary');
    const pSec = document.getElementById('val-pressure-secondary');
    const pBar = Math.max(0, data.pressure.bar || 0);
    const pPsi = Math.max(0, data.pressure.psi || 0);

    if (pPri) pPri.textContent = data.device.esp32_connected ? pVal : '--';
    if (pUnitEl) pUnitEl.textContent = pUnit;
    if (pSec) {
      pSec.textContent = data.device.esp32_connected
        ? `${pBar} bar (${pPsi} PSI)`
        : 'ESP32 Disconnected (No Signal)';
    }

    const pFill = document.getElementById('pressure-progress');
    if (pFill) {
      const pPct = data.pressure.percentage || 0;
      pFill.style.width = `${Math.min(100, Math.max(0, pPct))}%`;
      if (!data.device.esp32_connected) {
        pFill.style.background = '#64748b';
      } else if (data.status.level === 'CRITICAL') {
        pFill.style.background = 'var(--status-critical)';
      } else if (data.status.level === 'LOW_PRESSURE') {
        pFill.style.background = 'var(--status-warning)';
      } else {
        pFill.style.background = 'linear-gradient(90deg, var(--blue-primary), var(--teal-primary))';
      }
    }

    // Card B: Flow
    if (data.flow && typeof data.flow.prescribed === 'number') {
      currentPrescribedFlow = data.flow.prescribed;
    }
    const fVal = (data.history && data.history.length > 0)
      ? data.history[data.history.length - 1].flow_lpm
      : (data.flow.value ?? 0.0);
    const fPri = document.getElementById('val-flow-primary');
    const fPres = document.getElementById('val-flow-prescribed');
    const fFill = document.getElementById('flow-progress');
    const fDiff = document.getElementById('flow-diff-label');

    if (fPri) fPri.textContent = data.device.esp32_connected ? fVal.toFixed(1) : '0.0';
    if (fPres) fPres.textContent = data.device.esp32_connected ? `Prescribed: ${data.flow.prescribed.toFixed(1)} L/min` : 'Flow: 0.0 L/min (Sensor Offline)';
    if (fFill) fFill.style.width = data.device.esp32_connected ? `${Math.min(100, (fVal / 10.0) * 100)}%` : '0%';
    if (fDiff) {
      if (data.device.esp32_connected) {
        const flowDiff = (fVal - data.flow.prescribed).toFixed(1);
        fDiff.textContent = `${flowDiff > 0 ? '+' : ''}${flowDiff} L/min delta`;
      } else {
        fDiff.textContent = 'Hardware Offline';
      }
    }

    const flowTag = document.getElementById('flow-tag');
    if (flowTag) {
      if (!data.device.esp32_connected) {
        flowTag.textContent = 'Sensor Offline';
        flowTag.className = 'badge-tag text-slate-400 bg-slate-800';
      } else if (data.device.data_source?.includes('HARDWARE') || !data.flow.is_simulated) {
        flowTag.textContent = 'Live Flow Sensor';
        flowTag.className = 'badge-tag text-emerald-400 bg-emerald-950/60 border border-emerald-800/40';
      } else {
        flowTag.textContent = 'Simulated Flow';
        flowTag.className = 'badge-tag';
      }
    }

    // Card C: ETE
    const etePri = document.getElementById('val-ete-primary');
    const eteLit = document.getElementById('val-ete-litres');
    if (etePri) etePri.textContent = data.ete.display;
    if (eteLit) {
      if (data.ete.valid) {
        eteLit.textContent = `Est. Usable: ~${data.ete.remaining_litres} L remaining`;
      } else {
        eteLit.textContent = data.ete.reason || 'Estimate unavailable';
      }
    }

    // Card D: Status
    const badge = document.getElementById('val-status-badge');
    if (badge) {
      badge.textContent = data.status.label;
      badge.className = `status-pill-large ${data.status.badge_class}`;
    }

    const iconWrap = document.getElementById('status-icon-wrap');
    const statusDesc = document.getElementById('val-status-desc');
    if (iconWrap && statusDesc) {
      if (data.hardware_bridge && data.hardware_bridge.status === 'busy') {
        iconWrap.className = 'icon-wrap orange';
        statusDesc.textContent = `${data.hardware_bridge.detected_port} is busy. Close the Serial Monitor tab in Arduino IDE to auto-connect.`;
      } else if (!data.device.esp32_connected || data.status.level === 'SENSOR_DISCONNECTED') {
        iconWrap.className = 'icon-wrap gray';
        statusDesc.textContent = 'ESP32 disconnected or offline. Connect ESP32 via USB or Bluetooth to resume live telemetry.';
      } else if (data.status.level === 'CRITICAL') {
        iconWrap.className = 'icon-wrap red';
        statusDesc.textContent = 'Urgent: Reserve nearing exhaustion. Stage replacement cylinder.';
      } else if (data.status.level === 'LOW_PRESSURE') {
        iconWrap.className = 'icon-wrap orange';
        statusDesc.textContent = 'Warning: Pressure below configured clinical threshold.';
      } else {
        iconWrap.className = 'icon-wrap green';
        statusDesc.textContent = 'All telemetry parameters within normal operational envelope.';
      }
    }

    // Alert Badges
    const alertCount = data.active_alerts_count || 0;
    const hNotif = document.getElementById('header-notif-badge');
    const navNotif = document.getElementById('nav-alert-count');
    const actTag = document.getElementById('val-active-alerts-tag');
    if (hNotif) hNotif.textContent = alertCount;
    if (navNotif) navNotif.textContent = alertCount;
    if (actTag) actTag.textContent = `${alertCount} Active Alert${alertCount === 1 ? '' : 's'}`;

    // Overview Fleet Table
    renderOverviewFleetTable();
  }

  // ═════════════════════════════════════════════════════════════════════════
  // 9. FLEET & CYLINDERS VIEW
  // ═════════════════════════════════════════════════════════════════════════
  async function renderOverviewFleetTable() {
    try {
      const data = await OxyAPI.getCylinders('', 'ALL');
      const tbody = document.getElementById('tbody-overview-cylinders');
      if (!tbody) return;
      tbody.innerHTML = '';

      data.cylinders.slice(0, 4).forEach(c => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td><strong>${c.id}</strong></td>
          <td>${c.ward}</td>
          <td>${c.pressure_psi} PSI <span class="text-muted">(${c.pressure_bar} bar)</span></td>
          <td>${c.ete}</td>
          <td><span class="status-pill-large badge-${c.status.toLowerCase()}">${formatStatus(c.status)}</span></td>
        `;
        tbody.appendChild(tr);
      });
    } catch (err) {
      console.error('Fleet preview error:', err);
    }
  }

  async function loadCylinderFleet(showSpinner = true) {
    const searchVal = document.getElementById('input-cylinder-search')?.value || '';
    const statusVal = document.getElementById('select-cylinder-status')?.value || 'ALL';
    const tbody = document.getElementById('tbody-fleet-cylinders');
    if (!tbody) return;

    try {
      const data = await OxyAPI.getCylinders(searchVal, statusVal);
      tbody.innerHTML = '';

      if (!data.cylinders.length) {
        tbody.innerHTML = `<tr><td colspan="9" style="text-align:center;padding:30px;color:#94a3b8;">No cylinders match the specified filter.</td></tr>`;
        return;
      }

      data.cylinders.forEach(c => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td><strong>${c.id}</strong></td>
          <td>${c.ward}<br><small class="text-muted">${c.patient}</small></td>
          <td>${c.type}</td>
          <td><strong>${c.pressure_psi} PSI</strong> <br><small class="text-muted">${c.pressure_bar} bar</small></td>
          <td>${c.flow_lpm.toFixed(1)} L/min</td>
          <td><strong>${c.ete}</strong></td>
          <td><span class="status-pill-large badge-${c.status.toLowerCase()}">${formatStatus(c.status)}</span></td>
          <td><small class="font-mono text-muted">${c.sensor_id}</small></td>
          <td style="white-space:nowrap;">
            <button class="btn btn-primary-sm btn-monitor-cyl" data-id="${c.id}" title="Monitor live pressure & flow on Overview">
              <i data-lucide="radio" class="w-3.5 h-3.5"></i> Live
            </button>
            <button class="btn btn-outline-sm btn-view-cyl-detail" data-id="${c.id}">
              Details
            </button>
          </td>
        `;
        tbody.appendChild(tr);
      });

      // Bind quick monitor live triggers
      document.querySelectorAll('.btn-monitor-cyl').forEach(b => {
        b.addEventListener('click', async () => {
          const id = b.getAttribute('data-id');
          await changeActiveCylinder(id);
          switchView('view-overview');
        });
      });

      // Bind modal detail triggers
      document.querySelectorAll('.btn-view-cyl-detail').forEach(b => {
        b.addEventListener('click', () => openCylinderModal(b.getAttribute('data-id')));
      });
      if (window.lucide) lucide.createIcons();
    } catch (err) {
      console.error('Error loading cylinder fleet:', err);
    }
  }

  document.getElementById('input-cylinder-search')?.addEventListener('keyup', () => loadCylinderFleet(false));
  document.getElementById('select-cylinder-status')?.addEventListener('change', () => loadCylinderFleet(false));

  async function openCylinderModal(cylId) {
    try {
      const res = await OxyAPI.getCylinderDetail(cylId);
      if (!res.success) return;
      const c = res.cylinder;
      document.getElementById('modal-cylinder-id').textContent = `${c.id} — Diagnostic Specification`;
      document.getElementById('modal-content').innerHTML = `
        <div class="modal-detail-grid">
          <div><strong class="modal-label">Ward / Location:</strong><br><span class="modal-val">${c.ward}</span></div>
          <div><strong class="modal-label">Assigned Patient:</strong><br><span class="modal-val">${c.patient}</span></div>
          <div><strong class="modal-label">Cylinder Model:</strong><br><span class="modal-val">${c.type} (${c.capacity_l} L capacity)</span></div>
          <div><strong class="modal-label">Telemetry Node:</strong><br><code class="modal-code">${c.sensor_id}</code> <span class="modal-val">(Battery: ${c.battery_pct}%)</span></div>
          <div><strong class="modal-label">Current Pressure:</strong><br><span class="modal-val-lg">${c.pressure_psi} PSI</span> <span class="modal-val-sub">(${c.pressure_bar} bar)</span></div>
          <div><strong class="modal-label">Flow Rate:</strong><br><span class="modal-val-lg">${c.flow_lpm} L/min</span></div>
          <div><strong class="modal-label">Estimated Time Remaining:</strong><br><span class="modal-val-lg text-teal">${c.ete}</span></div>
          <div><strong class="modal-label">Operational Status:</strong><br><span class="status-pill-large badge-${c.status.toLowerCase()}">${formatStatus(c.status)}</span></div>
        </div>
        <div style="margin-bottom:16px;display:flex;justify-content:flex-end;">
          <button class="btn btn-primary" id="btn-modal-monitor-live" data-id="${c.id}">
            <i data-lucide="radio"></i> Monitor Live on Overview
          </button>
        </div>
        <div class="ete-disclaimer-box">
          <span>⚠️ All displayed telemetry metrics reflect software demonstration data. For real clinical decisions, inspect certified mechanical gauges.</span>
        </div>
      `;

      document.getElementById('btn-modal-monitor-live')?.addEventListener('click', async () => {
        await changeActiveCylinder(c.id);
        document.getElementById('cylinder-modal').classList.remove('active');
        switchView('view-overview');
      });

      document.getElementById('cylinder-modal').classList.add('active');
      if (window.lucide) lucide.createIcons();
    } catch (err) {
      console.error('Modal detail fetch error:', err);
    }
  }

  document.getElementById('modal-close')?.addEventListener('click', () => {
    document.getElementById('cylinder-modal').classList.remove('active');
  });

  document.getElementById('cylinder-modal')?.addEventListener('click', (e) => {
    if (e.target.id === 'cylinder-modal') {
      document.getElementById('cylinder-modal').classList.remove('active');
    }
  });

  // ═════════════════════════════════════════════════════════════════════════
  // 10. ALERTS & SIMULATION CONTROLS
  // ═════════════════════════════════════════════════════════════════════════
  async function loadAlertsView(isManualClick = false) {
    const refreshBtn = document.getElementById('btn-refresh-alerts');
    const icon = refreshBtn?.querySelector('i');
    if (isManualClick && icon) {
      icon.classList.add('animate-spin');
    }

    try {
      const data = await OxyAPI.getAlerts();
      const activeContainer = document.getElementById('active-alerts-container');
      const histContainer = document.getElementById('historical-alerts-container');
      if (!activeContainer || !histContainer) return;

      activeContainer.innerHTML = '';
      histContainer.innerHTML = '';

      const unack = data.alerts.filter(a => !a.acknowledged);
      const ack = data.alerts.filter(a => a.acknowledged);

      const counter = document.getElementById('active-alert-counter');
      if (counter) counter.textContent = `${unack.length} Active`;

      if (!unack.length) {
        activeContainer.innerHTML = `<div class="nominal-alerts-banner">All telemetry nominal. No active unacknowledged alerts.</div>`;
      } else {
        unack.forEach(a => {
          const div = document.createElement('div');
          div.className = `alert-item severity-${a.severity.toLowerCase()}`;
          const iconType = a.severity === 'CRITICAL' ? 'alert-triangle' : (a.severity === 'WARNING' ? 'alert-circle' : 'info');
          const boxClass = a.severity === 'CRITICAL' ? 'crit' : (a.severity === 'WARNING' ? 'warn' : 'info');
          div.innerHTML = `
            <div class="alert-left">
              <div class="alert-icon-box ${boxClass}">
                <i data-lucide="${iconType}"></i>
              </div>
              <div>
                <div class="alert-title">${a.title}</div>
                <div class="alert-desc">${a.description}</div>
                <div class="alert-meta">Timestamp: ${a.timestamp} · Severity: ${a.severity}</div>
              </div>
            </div>
            <button class="btn btn-outline-sm btn-ack-alert" data-id="${a.id}">
              Acknowledge
            </button>
          `;
          activeContainer.appendChild(div);
        });
      }

      ack.forEach(a => {
        const div = document.createElement('div');
        div.className = `alert-item severity-${a.severity.toLowerCase()}`;
        div.style.opacity = '0.75';
        div.innerHTML = `
          <div class="alert-left">
            <div class="alert-icon-box info">
              <i data-lucide="check"></i>
            </div>
            <div>
              <div class="alert-title">${a.title}</div>
              <div class="alert-desc">${a.description}</div>
              <div class="alert-meta">Logged: ${a.timestamp} · Acknowledged by Ward Staff</div>
            </div>
          </div>
        `;
        histContainer.appendChild(div);
      });

      // Bind Acknowledge Buttons
      document.querySelectorAll('.btn-ack-alert').forEach(btn => {
        btn.addEventListener('click', async () => {
          const alertId = btn.getAttribute('data-id');
          await OxyAPI.acknowledgeAlert(alertId);
          showToast(`Alert ${alertId} acknowledged and resolved.`);
          loadAlertsView();
          pollLiveTelemetry();
        });
      });

      if (window.lucide) lucide.createIcons();

      if (isManualClick) {
        showToast(`Alerts refreshed: ${unack.length} active alarms`);
      }
    } catch (err) {
      console.error('Error loading alerts:', err);
      if (isManualClick) {
        showToast('Failed to refresh alerts');
      }
    } finally {
      if (icon) {
        setTimeout(() => icon.classList.remove('animate-spin'), 500);
      }
    }
  }

  document.getElementById('btn-refresh-alerts')?.addEventListener('click', () => {
    loadAlertsView(true);
    pollLiveTelemetry();
  });

  // Simulation Scenario Triggers
  document.getElementById('btn-sim-low')?.addEventListener('click', async () => {
    await OxyAPI.triggerScenario('LOW_PRESSURE');
    showToast('Simulation: Low Supply condition activated (42 Bar / 609 PSI)');
    pollLiveTelemetry();
    loadAlertsView();
    loadAiInsights();
  });

  document.getElementById('btn-sim-disconnect')?.addEventListener('click', async () => {
    await OxyAPI.triggerScenario('SENSOR_DISCONNECTED');
    showToast('Simulation: Sensor Disconnected / Telemetry Lost');
    pollLiveTelemetry();
    loadAlertsView();
    loadAiInsights();
  });

  document.getElementById('btn-sim-reset')?.addEventListener('click', async () => {
    const res = await OxyAPI.triggerScenario('RESET');
    const msg = res?.message || 'Oxygen Cylinder Refilled: Supply restored to full nominal pressure';
    showToast(msg);
    pollLiveTelemetry();
    loadAlertsView();
    if (currentView === 'view-cylinders') {
      loadCylinderFleet(true);
    }
    loadAiInsights();
  });

  // ═════════════════════════════════════════════════════════════════════════
  // 11. AI INSIGHTS VIEW
  // ═════════════════════════════════════════════════════════════════════════
  async function loadAiInsights() {
    try {
      const ovSum = document.getElementById('ai-overview-summary');
      const mainSum = document.getElementById('ai-main-summary');
      if (ovSum) ovSum.style.opacity = '0.7';
      if (mainSum) mainSum.style.opacity = '0.7';

      const data = await OxyAPI.getAiInsights(activeCylinderId);

      const engFull = document.getElementById('ai-engine-full-name');
      const engTag = document.getElementById('ai-engine-tag');
      const timeEl = document.getElementById('ai-timestamp');

      if (ovSum) ovSum.style.opacity = '1';
      if (mainSum) mainSum.style.opacity = '1';

      if (engFull) engFull.textContent = data.engine;
      if (engTag) engTag.textContent = data.is_llm_active ? 'Groq Cloud LLM' : 'Rule Engine';
      if (timeEl) timeEl.textContent = `Last analyzed: ${data.timestamp}${data.diagnostic && data.diagnostic.latency_ms ? ` (${data.diagnostic.latency_ms}ms)` : ''}`;
      if (mainSum) mainSum.textContent = data.summary;
      if (ovSum) ovSum.textContent = data.summary;

      const groqStatusEl = document.getElementById('groq-live-status-text');
      if (groqStatusEl && data.diagnostic) {
        if (data.diagnostic.status === 'SUCCESS') {
          groqStatusEl.innerHTML = `<span style="color:#34d399;font-weight:600;">● Live Cloud Connected</span>: <code>${data.diagnostic.model}</code> responded in <strong>${data.diagnostic.latency_ms}ms</strong>.`;
        } else if (data.diagnostic.groq_configured) {
          groqStatusEl.innerHTML = `<span style="color:#fbbf24;font-weight:600;">⚠️ Groq Notice</span>: ${data.diagnostic.status}`;
        } else {
          groqStatusEl.textContent = 'Offline deterministic mode active. Add GROQ_API_KEY to .env to enable cloud synthesis.';
        }
      }

      const ovActions = document.getElementById('ai-overview-actions');
      if (ovActions) {
        ovActions.innerHTML = '';
        data.operational_suggestions.slice(0, 2).forEach(act => {
          ovActions.innerHTML += `<div class="ai-action-item"><i data-lucide="check-circle-2"></i><span>${act}</span></div>`;
        });
      }

      // Populate Conditions
      const condList = document.getElementById('ai-conditions-list');
      if (condList) {
        condList.innerHTML = '';
        data.detected_conditions.forEach(c => {
          condList.innerHTML += `<li>${c}</li>`;
        });
      }

      // Populate Actions
      const actContainer = document.getElementById('ai-actions-container');
      if (actContainer) {
        actContainer.innerHTML = '';
        data.operational_suggestions.forEach(act => {
          actContainer.innerHTML += `<div class="action-pill-item"><i data-lucide="arrow-right-circle"></i> ${act}</div>`;
        });
      }

      // Populate Triggers
      const trigBox = document.getElementById('ai-triggers-box');
      if (trigBox) {
        trigBox.innerHTML = '';
        data.trigger_rules.forEach(r => {
          trigBox.innerHTML += `<div class="rule-code-tag">${r}</div>`;
        });
      }

      if (window.lucide) lucide.createIcons();
    } catch (err) {
      console.error('AI Insights load error:', err);
    }
  }

  document.getElementById('btn-refresh-ai')?.addEventListener('click', () => {
    showToast('Re-analyzing telemetry...');
    loadAiInsights();
  });

  // ═════════════════════════════════════════════════════════════════════════
  // 12. HISTORICAL REPORTS VIEW
  // ═════════════════════════════════════════════════════════════════════════
  async function loadHistoryTable() {
    try {
      const histSelect = document.getElementById('history-select-cylinder');
      if (histSelect) histSelect.value = activeCylinderId;

      const limitVal = 500;

      const histTag = document.getElementById('history-active-cyl-tag');
      if (histTag) histTag.textContent = `Monitoring: ${activeCylinderId}`;

      const csvBtn = document.getElementById('btn-export-csv');
      if (csvBtn) {
        csvBtn.href = `/api/export-csv?cylinder_id=${encodeURIComponent(activeCylinderId)}`;
        csvBtn.setAttribute('download', `oxysense_${activeCylinderId.toLowerCase()}_report.csv`);
      }

      // Query SQLite database for complete historical records
      const dbData = await OxyAPI.getCylinderTelemetry(activeCylinderId, limitVal);
      const totalBadge = document.getElementById('history-total-count-badge');
      if (totalBadge && dbData.total_records !== undefined) {
        totalBadge.textContent = `${dbData.total_records.toLocaleString()} Logged in DB`;
      }

      if (dbData && dbData.telemetry && dbData.telemetry.length > 0) {
        renderHistoryRows(dbData.telemetry);
      } else {
        const fallback = await OxyAPI.getHistory('24h', activeCylinderId);
        renderHistoryRows(fallback.points || []);
      }
    } catch (err) {
      console.error('History load error:', err);
    }
  }

  function renderHistoryRows(points) {
    const tbody = document.getElementById('tbody-history-logs');
    if (!tbody || !points) return;
    tbody.innerHTML = '';

    // Show all records (up to 250 rows), newest first
    const reversed = [...points].reverse();
    reversed.forEach(p => {
      const tr = document.createElement('tr');
      const timeDisplay = p.timestamp ? (p.timestamp.includes(' ') ? p.timestamp.split(' ')[1] : p.timestamp) : '--:--';
      const pPsi = p.pressure_psi ?? Math.round((p.pressure_bar || 0) * 14.5038);
      const fLpm = (p.flow_rate_lpm ?? p.flow_lpm ?? 0).toFixed(2);
      const remPct = p.remaining_pct ?? Math.round(((p.pressure_bar || 0) / 200.0) * 100);
      const eteStr = p.ete_minutes ? `${Math.floor(p.ete_minutes / 60)}h ${Math.round(p.ete_minutes % 60)}m` : (p.pressure_bar > 0 ? `${Math.floor(p.pressure_bar / 20)}h` : '0h 00m');
      const statusStr = p.status || (p.pressure_bar <= 20 ? 'CRITICAL' : p.pressure_bar <= 50 ? 'LOW_PRESSURE' : 'NORMAL');
      const verificationTag = p.data_source === 'HARDWARE_ESP32' ? 'Hardware Verified' : 'Database Logged';

      tr.innerHTML = `
        <td>${timeDisplay}</td>
        <td>${p.pressure_bar}</td>
        <td><strong>${pPsi}</strong></td>
        <td>${fLpm}</td>
        <td>${remPct}%</td>
        <td>${eteStr}</td>
        <td><span class="status-pill-large badge-${statusStr.toLowerCase()}">${formatStatus(statusStr)}</span></td>
        <td><span class="badge-tag">${verificationTag}</span></td>
      `;
      tbody.appendChild(tr);
    });
  }

  // ═════════════════════════════════════════════════════════════════════════
  // 13. SETTINGS VIEW
  // ═════════════════════════════════════════════════════════════════════════
  async function loadSettingsForm() {
    try {
      const res = await OxyAPI.getSettings();
      const cfg = res.config;
      document.getElementById('setting-warning').value = cfg.warning_threshold_bar;
      document.getElementById('setting-critical').value = cfg.critical_threshold_bar;
      document.getElementById('setting-prescribed').value = cfg.prescribed_flow_lpm;
      document.getElementById('setting-capacity').value = cfg.cylinder_capacity_litres;
      document.getElementById('setting-unit').value = cfg.pressure_unit;
    } catch (err) {
      console.error('Settings load error:', err);
    }
  }

  document.getElementById('form-settings')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const payload = {
      warning_threshold_bar: document.getElementById('setting-warning').value,
      critical_threshold_bar: document.getElementById('setting-critical').value,
      prescribed_flow_lpm: document.getElementById('setting-prescribed').value,
      cylinder_capacity_litres: document.getElementById('setting-capacity').value,
      pressure_unit: document.getElementById('setting-unit').value
    };
    try {
      await OxyAPI.saveSettings(payload);
      showToast('Settings saved successfully!');
      pollLiveTelemetry();
    } catch (err) {
      showToast('Failed to save settings');
    }
  });

  // Range pill buttons on chart
  document.querySelectorAll('.btn-pill').forEach(pill => {
    pill.addEventListener('click', async () => {
      document.querySelectorAll('.btn-pill').forEach(p => p.classList.remove('active'));
      pill.classList.add('active');
      const r = pill.getAttribute('data-range');
      const hist = await OxyAPI.getHistory(r, activeCylinderId);
      OxyCharts.updateFromHistory(hist.points, currentPrescribedFlow);
    });
  });

  // ═════════════════════════════════════════════════════════════════════════
  // 13B. INSTITUTIONAL USER MANAGEMENT (ADMIN ONLY)
  // ═════════════════════════════════════════════════════════════════════════
  async function loadAdminUsers() {
    const tbody = document.getElementById('tbody-users');
    if (!tbody) return;
    tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; padding: 20px;">Loading personnel directory...</td></tr>';

    try {
      const res = await OxyAPI.getAdminUsers();
      if (!res.success || !res.users) {
        tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--status-critical); padding: 20px;">${res.error || 'Failed to load users'}</td></tr>`;
        return;
      }

      if (res.users.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; padding: 20px;">No registered personnel found.</td></tr>';
        return;
      }

      const isMainAdmin = Boolean(currentUser && (currentUser.is_main_admin || currentUser.role === 'MAIN_ADMIN'));

      const renderRow = (u) => {
        const isSelf = currentUser && currentUser.id === u.id;
        let roleBadge = '<span class="badge-tag">Viewer</span>';
        if (u.is_main_admin || u.role === 'MAIN_ADMIN') {
          roleBadge = '<span class="badge-tag-ai" style="background: rgba(13, 148, 136, 0.25); color: #2dd4bf;">Main Admin</span>';
        } else if (u.role === 'ADMIN') {
          roleBadge = '<span class="badge-tag" style="background: rgba(2, 132, 199, 0.25); color: #38bdf8;">Admin</span>';
        }

        const verifyBadge = u.is_verified
          ? '<span style="color: #34d399; font-weight: 600;">✓ Verified</span>'
          : '<span style="color: #f59e0b; font-weight: 600;">⏳ Pending</span>';

        const statusBadge = u.status === 'ACTIVE'
          ? '<span class="status-pill status-normal" style="font-size: 0.72rem; padding: 2px 8px;">Active</span>'
          : '<span class="status-pill status-critical" style="font-size: 0.72rem; padding: 2px 8px;">Suspended</span>';

        let actionsHtml = '';
        if (u.is_main_admin) {
          actionsHtml = '<span style="color: var(--text-muted); font-size: 0.75rem;">System Owner</span>';
        } else {
          if (isMainAdmin) {
            if (u.role === 'VIEWER') {
              actionsHtml += `<button class="btn btn-sm btn-outline-teal btn-change-role" data-id="${u.id}" data-role="ADMIN" style="padding: 3px 8px; font-size: 0.72rem; margin-right: 6px;">Promote Admin</button>`;
            } else if (u.role === 'ADMIN') {
              actionsHtml += `<button class="btn btn-sm btn-outline-secondary btn-change-role" data-id="${u.id}" data-role="VIEWER" style="padding: 3px 8px; font-size: 0.72rem; margin-right: 6px;">Demote Viewer</button>`;
            }
          }

          if (!isSelf) {
            if (u.status === 'ACTIVE') {
              actionsHtml += `<button class="btn btn-sm btn-outline-critical btn-change-status" data-id="${u.id}" data-status="SUSPENDED" style="padding: 3px 8px; font-size: 0.72rem;">Suspend</button>`;
            } else {
              actionsHtml += `<button class="btn btn-sm btn-outline-teal btn-change-status" data-id="${u.id}" data-status="ACTIVE" style="padding: 3px 8px; font-size: 0.72rem;">Activate</button>`;
            }
          }
        }

        return `
          <tr style="border-bottom: 1px solid var(--border-color);">
            <td style="padding: 12px; font-weight: 600;">${u.full_name || u.name}</td>
            <td style="padding: 12px;"><code>${u.email}</code></td>
            <td style="padding: 12px; color: var(--text-muted);">${u.created_at || '—'}</td>
            <td style="padding: 12px; text-align: center;">${verifyBadge}</td>
            <td style="padding: 12px; text-align: center;">${roleBadge}</td>
            <td style="padding: 12px; text-align: center;">${statusBadge}</td>
            <td style="padding: 12px; text-align: right;">${actionsHtml}</td>
          </tr>
        `;
      };

      tbody.innerHTML = res.users.map(renderRow).join('');

      tbody.querySelectorAll('.btn-change-role').forEach(btn => {
        btn.addEventListener('click', async () => {
          const uId = btn.getAttribute('data-id');
          const newRole = btn.getAttribute('data-role');
          const r = await OxyAPI.modifyUserRole(uId, newRole);
          if (r.success) {
            showToast(r.message);
            loadAdminUsers();
          } else {
            showToast(`Role update failed: ${r.error}`);
          }
        });
      });

      tbody.querySelectorAll('.btn-change-status').forEach(btn => {
        btn.addEventListener('click', async () => {
          const uId = btn.getAttribute('data-id');
          const newStatus = btn.getAttribute('data-status');
          const r = await OxyAPI.modifyUserStatus(uId, newStatus);
          if (r.success) {
            showToast(r.message);
            loadAdminUsers();
          } else {
            showToast(`Status update failed: ${r.error}`);
          }
        });
      });

    } catch (err) {
      tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--status-critical); padding: 20px;">Error loading users: ${err.message}</td></tr>`;
    }
  }

  document.getElementById('btn-refresh-users')?.addEventListener('click', loadAdminUsers);
  document.getElementById('input-users-search')?.addEventListener('input', (e) => {
    const term = e.target.value.toLowerCase().trim();
    const rows = document.querySelectorAll('#tbody-users tr');
    rows.forEach(r => {
      const text = r.textContent.toLowerCase();
      r.style.display = text.includes(term) ? '' : 'none';
    });
  });

  // ═════════════════════════════════════════════════════════════════════════
  // 14. UTILITIES & TOASTS
  // ═════════════════════════════════════════════════════════════════════════
  function formatStatus(status) {
    if (status === 'NORMAL') return 'Normal';
    if (status === 'LOW_PRESSURE') return 'Low Supply';
    if (status === 'CRITICAL') return 'Critical';
    if (status === 'SENSOR_DISCONNECTED') return 'Disconnected';
    return status;
  }

  function showToast(message) {
    const container = document.getElementById('toast-container');
    if (!container) return;
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.innerHTML = `<i data-lucide="info"></i> <span>${message}</span>`;
    container.appendChild(toast);
    if (window.lucide) lucide.createIcons();

    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(10px)';
      toast.style.transition = 'all 0.3s ease';
      setTimeout(() => toast.remove(), 300);
    }, 3200);
  }

  // ═════════════════════════════════════════════════════════════════════════
  // INITIAL BOOTSTRAP
  // ═════════════════════════════════════════════════════════════════════════
  initSplashScreen();
  startStreaming();
  loadAiInsights();
});
