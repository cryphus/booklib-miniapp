/** Remarka Mini App entry point: Telegram bootstrap, auth, routing. */

import { ApiError, api } from './api/client.js';
import { applyThemeVariables, authenticate, hideBackButton, initTelegram, isTelegram } from './api/telegram.js';
import { navigate, refresh, route, startRouter } from './router.js';
import { invalidateAll, keys, query, setState } from './store.js';
import { fill, h } from './ui/dom.js';
import { errorState } from './ui/components.js';

import { splashScreen } from './screens/splash.js';
import { onboardingScreen } from './screens/onboarding.js';
import { libraryScreen } from './screens/library.js';
import { searchScreen } from './screens/search.js';
import { addBookScreen } from './screens/add-book.js';
import { editBookScreen } from './screens/edit-book.js';
import { bookScreen } from './screens/book.js';
import { entryFormScreen } from './screens/entry-form.js';
import { aiScreen } from './screens/ai.js';
import { aiHistoryScreen } from './screens/ai-history.js';
import { profileScreen } from './screens/profile.js';
import { premiumScreen } from './screens/premium.js';
import { settingsScreen } from './screens/settings.js';
import { accountScreen } from './screens/account.js';
import { supportScreen } from './screens/support.js';
import { legalScreen } from './screens/legal.js';

const root = document.getElementById('app');

/** Reflects Telegram's safe-area insets into the CSS variables the layout uses. */
function syncSafeArea() {
  const tg = window.Telegram && window.Telegram.WebApp;
  const inset = (tg && (tg.contentSafeAreaInset || tg.safeAreaInset)) || null;
  const style = document.documentElement.style;
  style.setProperty('--rm-safe-top', `${(inset && inset.top) || 0}px`);
  style.setProperty('--rm-safe-bottom', `${(inset && inset.bottom) || 0}px`);
}

function registerRoutes() {
  route('/', libraryScreen);
  route('/search', searchScreen);
  route('/books/add', addBookScreen);
  route('/book/:id', bookScreen);
  route('/book/:id/edit', editBookScreen);
  route('/book/:id/entry/new', entryFormScreen);
  route('/entry/:entryId/edit', entryFormScreen);
  route('/ai', aiScreen);
  route('/ai/history', aiHistoryScreen);
  route('/ai/:conversationId', aiScreen);
  route('/profile', profileScreen);
  route('/premium', premiumScreen);
  route('/settings', settingsScreen);
  route('/account', accountScreen);
  route('/support', supportScreen);
  route('/legal/:slug', legalScreen);
  route('/onboarding', onboardingScreen);
}

/**
 * Recovers from an invalidated session token (expired, or the server no longer knows it)
 * by signing in again once and re-rendering the current screen, instead of leaving every
 * screen in an error state. Rate-limited so a genuinely rejected login cannot loop.
 */
let reauthAt = 0;
let reauthInFlight = null;

async function handleSessionExpired() {
  const now = Date.now();
  if (reauthInFlight) return reauthInFlight;
  if (now - reauthAt < 30_000) return null;
  reauthAt = now;

  reauthInFlight = (async () => {
    try {
      await authenticate();
      invalidateAll();
      await loadSession();
      refresh();
    } catch (error) {
      showFatal(error);
    } finally {
      reauthInFlight = null;
    }
  })();
  return reauthInFlight;
}

/** Loads the values every screen depends on, so the first paint is never half-empty. */
async function loadSession() {
  const [me, billing] = await Promise.all([
    query(keys.me, () => api.getMe(), { ttl: 60_000 }),
    query(keys.billing, () => api.getBillingStatus(), { ttl: 30_000 }),
  ]);
  setState({ me, billing, aiUsage: me.ai_usage, ready: true });
  return me;
}

function applyTheme(theme) {
  const resolved =
    theme === 'system'
      ? (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.colorScheme) || 'light'
      : theme;
  document.documentElement.setAttribute('data-rm-theme', resolved);
}

async function boot() {
  initTelegram();
  syncSafeArea();
  applyThemeVariables();

  fill(root, splashScreen());

  try {
    api.onUnauthorized = handleSessionExpired;
    await authenticate();
    const me = await loadSession();
    applyTheme(me.preferences?.theme || 'system');

    registerRoutes();
    startRouter(root, {
      beforeRender: (current) => {
        // Telegram's own back button is managed per screen; reset it on every route.
        if (current.path === '/' || current.path === '/ai' || current.path === '/profile') {
          hideBackButton();
        }
      },
    });

    if (!me.onboarding_completed && !window.location.hash.startsWith('#/onboarding')) {
      navigate('/onboarding', { replace: true });
    } else if (!window.location.hash) {
      navigate('/', { replace: true });
    }
  } catch (error) {
    showFatal(error);
  }
}

/** Screen 02: the app could not start at all. */
function showFatal(error) {
  const isAuthProblem = error instanceof ApiError && (error.isUnauthorized || error.isForbidden);
  const text = isAuthProblem && !isTelegram()
    ? 'Откройте приложение через Telegram. В браузере вход доступен только в режиме разработки.'
    : 'Проверьте соединение и попробуйте снова';

  fill(root, 
    h('div', {
      style: {
        minHeight: '100dvh', display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: '0 24px',
      },
    },
      errorState({
        title: 'Не удалось загрузить приложение',
        text,
        onRetry: () => {
          invalidateAll();
          boot();
        },
      }),
    ),
  );
  if (!(error instanceof ApiError)) console.error(error);
}

window.addEventListener('resize', syncSafeArea);
boot();
