/**
 * Registry of open bottom sheets.
 *
 * Kept in its own module so the router can dismiss sheets on navigation without
 * importing components.js (which itself imports the router).
 */

const open = new Set();

export function overlayRoot() {
  return document.getElementById('overlays');
}

export function registerOverlay(handle) {
  open.add(handle);
  return () => open.delete(handle);
}

export function unregisterOverlay(handle) {
  open.delete(handle);
}

/** Closes every open sheet, running its own close handler so pending promises settle. */
export function closeAllOverlays() {
  for (const handle of [...open]) {
    try {
      handle.close();
    } catch {
      /* a broken handler must not block navigation */
    }
  }
  open.clear();
  const root = overlayRoot();
  if (root) root.replaceChildren();
  document.body.style.overflow = '';
}

export function hasOpenOverlay() {
  return open.size > 0;
}
