/**
 * Hash router. Hash-based so the Mini App works from any static host and survives
 * a Telegram reload without server rewrites.
 *
 * Routes: '/', '/book/:id', '/book/:id/entry/new', '/entry/:id/edit', '/search',
 *         '/ai', '/ai/:conversationId', '/ai/history', '/profile', '/premium',
 *         '/settings', '/account', '/support', '/legal/:slug', '/books/add', ...
 */

import { fill } from './ui/dom.js';
import { closeAllOverlays } from './ui/overlays.js';

const routes = [];
let currentCleanup = null;
let currentRoute = null;

/** @param {string} pattern @param {(ctx: {params: object, query: URLSearchParams}) => Node|Promise<Node>} handler */
export function route(pattern, handler) {
  const names = [];
  const regex = new RegExp(
    '^' +
      pattern
        .replace(/\/:([A-Za-z0-9_]+)/g, (_m, name) => {
          names.push(name);
          return '/([^/]+)';
        })
        .replace(/\*/g, '.*') +
      '$',
  );
  routes.push({ pattern, regex, names, handler });
}

export function parseHash(hash = window.location.hash) {
  const raw = hash.replace(/^#/, '') || '/';
  const [path, search = ''] = raw.split('?');
  return { path: path || '/', query: new URLSearchParams(search) };
}

export function navigate(path, { replace = false } = {}) {
  const target = `#${path.startsWith('/') ? path : `/${path}`}`;
  if (window.location.hash === target) {
    resolve();
    return;
  }
  if (replace) window.location.replace(target);
  else window.location.hash = target;
}

export function back(fallback = '/') {
  if (window.history.length > 1) window.history.back();
  else navigate(fallback, { replace: true });
}

export function currentPath() {
  return parseHash().path;
}

let container = null;
let onBeforeRender = null;

export function startRouter(rootElement, { beforeRender } = {}) {
  container = rootElement;
  onBeforeRender = beforeRender || null;
  window.addEventListener('hashchange', resolve);
  resolve();
}

async function resolve() {
  const { path, query } = parseHash();
  const match = routes
    .map((r) => ({ r, m: r.regex.exec(path) }))
    .find((entry) => entry.m !== null);

  // A sheet belongs to the screen that opened it.
  closeAllOverlays();

  if (typeof currentCleanup === 'function') {
    try {
      currentCleanup();
    } catch {
      /* a screen teardown must never block navigation */
    }
    currentCleanup = null;
  }

  if (!match) {
    navigate('/', { replace: true });
    return;
  }

  const params = {};
  match.r.names.forEach((name, index) => {
    params[name] = decodeURIComponent(match.m[index + 1]);
  });

  currentRoute = { path, pattern: match.r.pattern, params, query };
  if (onBeforeRender) onBeforeRender(currentRoute);

  const result = await match.r.handler({ params, query, path });
  const node = Array.isArray(result) ? result[0] : result;
  const cleanup = Array.isArray(result) ? result[1] : result && result.__cleanup;
  if (typeof cleanup === 'function') currentCleanup = cleanup;

  if (container && node) {
    fill(container, node);
    // Every route starts at the top; screens that restore scroll do it themselves.
    window.scrollTo(0, 0);
  }
}

export function getCurrentRoute() {
  return currentRoute;
}

export function refresh() {
  resolve();
}
