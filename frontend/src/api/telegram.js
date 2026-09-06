/**
 * Telegram WebApp bootstrap.
 *
 * Wraps window.Telegram.WebApp so every call is safe in a plain browser during
 * development: outside Telegram each helper degrades to a no-op instead of throwing.
 */

import { api } from './client.js';

/** @returns {any|null} */
export function webApp() {
  return (typeof window !== 'undefined' && window.Telegram && window.Telegram.WebApp) || null;
}

export function isTelegram() {
  const tg = webApp();
  return Boolean(tg && tg.initData);
}

/** Call once on startup: ready(), expand(), theme colours, safe area. */
export function initTelegram() {
  const tg = webApp();
  if (!tg) return null;
  try {
    tg.ready();
    tg.expand();
    if (tg.setHeaderColor && tg.themeParams && tg.themeParams.bg_color) {
      tg.setHeaderColor(tg.themeParams.bg_color);
    }
    applyThemeVariables();
    if (tg.onEvent) tg.onEvent('themeChanged', applyThemeVariables);
  } catch {
    /* older Telegram clients lack some of these methods */
  }
  return tg;
}

/** Mirrors Telegram theme params onto CSS custom properties (--tg-*). */
export function applyThemeVariables() {
  const tg = webApp();
  if (!tg || !tg.themeParams || typeof document === 'undefined') return;
  const root = document.documentElement;
  for (const [key, value] of Object.entries(tg.themeParams)) {
    root.style.setProperty(`--tg-${key.replace(/_/g, '-')}`, value);
  }
  if (tg.colorScheme) root.setAttribute('data-tg-scheme', tg.colorScheme);
  const inset = tg.safeAreaInset || tg.contentSafeAreaInset;
  if (inset) {
    root.style.setProperty('--tg-safe-top', `${inset.top || 0}px`);
    root.style.setProperty('--tg-safe-bottom', `${inset.bottom || 0}px`);
  }
}

/**
 * Signs in. Inside Telegram the raw initData string is sent to the backend, which
 * verifies its signature; outside Telegram the development login is used instead.
 *
 * @param {{ devTelegramId?: number, devName?: string }} [options]
 */
export async function authenticate(options = {}) {
  const tg = webApp();
  if (tg && tg.initData) {
    return api.authTelegram(tg.initData);
  }
  // Browser development mode. The backend only accepts this while APP_ENV=development.
  return api.authDev(options.devTelegramId || 100500, options.devName || 'Dev');
}

/** Telegram BackButton, safely ignored in a plain browser. */
export function showBackButton(handler) {
  const tg = webApp();
  if (!tg || !tg.BackButton) return () => {};
  tg.BackButton.show();
  tg.BackButton.onClick(handler);
  return () => {
    try {
      tg.BackButton.offClick(handler);
      tg.BackButton.hide();
    } catch {
      /* ignore */
    }
  };
}

export function hideBackButton() {
  const tg = webApp();
  if (tg && tg.BackButton) tg.BackButton.hide();
}

/** @param {'light'|'medium'|'heavy'|'success'|'warning'|'error'|'selection'} kind */
export function haptic(kind = 'light') {
  const tg = webApp();
  const haptics = tg && tg.HapticFeedback;
  if (!haptics) return;
  try {
    if (kind === 'selection') haptics.selectionChanged();
    else if (['success', 'warning', 'error'].includes(kind)) haptics.notificationOccurred(kind);
    else haptics.impactOccurred(kind);
  } catch {
    /* ignore */
  }
}

/**
 * Opens a Telegram Stars invoice and resolves with its final status.
 * Outside Telegram it resolves to 'unsupported' so the UI can explain why.
 *
 * @param {string} invoiceUrl
 * @returns {Promise<'paid'|'cancelled'|'failed'|'pending'|'unsupported'>}
 */
export function openInvoice(invoiceUrl) {
  const tg = webApp();
  if (!tg || !tg.openInvoice) return Promise.resolve('unsupported');
  return new Promise((resolve) => {
    try {
      tg.openInvoice(invoiceUrl, (status) => resolve(status));
    } catch {
      resolve('failed');
    }
  });
}

export function closeApp() {
  const tg = webApp();
  if (tg && tg.close) tg.close();
}
