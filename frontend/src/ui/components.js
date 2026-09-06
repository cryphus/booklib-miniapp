/** Shared UI built from the design canvas patterns. */

import { ApiError, errorMessage } from '../api/client.js';
import { haptic, showBackButton } from '../api/telegram.js';
import { back, currentPath, navigate } from '../router.js';
import { aiAvatar, icons } from './icons.js';
import { append, clear, h, svg } from './dom.js';
import { overlayRoot, registerOverlay, unregisterOverlay } from './overlays.js';

// ------------------------------------------------------------------ screen shell

/**
 * A screen: optional header, a scrollable body, and the tab bar when requested.
 * @param {{ tab?: 'library'|'ai'|'profile'|null, header?: Node|null, footer?: Node|null,
 *           fab?: Node|null, padded?: boolean }} options
 */
export function screen(options, ...children) {
  const { tab = null, header = null, footer = null, fab = null, padded = true } = options;
  const body = h('div', { class: tab ? 'rm-scroll' : 'rm-scroll rm-scroll--plain' });
  if (!padded) body.style.padding = '0';
  if (footer) body.style.paddingBottom = '150px';
  append(body, children);

  return h('div', { style: { display: 'flex', flexDirection: 'column', minHeight: '100dvh' } },
    header,
    body,
    fab,
    footer,
    tab ? tabBar(tab) : null,
  );
}

/** Large page header used by Library / AI / Profile. */
export function pageHeader(title, subtitle, actions = null) {
  return h('div', {
    style: {
      display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between',
      paddingTop: '8px',
    },
  },
    h('div', null,
      h('div.rm-title', null, title),
      subtitle ? h('div.rm-subtitle', null, subtitle) : null,
    ),
    actions ? h('div', { style: { display: 'flex', gap: '8px', paddingTop: '6px' } }, actions) : null,
  );
}

/** Compact header with a back button, as on the book / form screens. */
export function backHeader(title, subtitle, right = null, { onBack } = {}) {
  const handler = onBack || (() => back());
  return h('div', {
    style: {
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      gap: '14px', padding: '10px 20px 6px',
    },
  },
    h('div', { style: { display: 'flex', alignItems: 'center', gap: '14px', minWidth: 0 } },
      h('button.rm-icon-btn', { onClick: () => { haptic('light'); handler(); }, 'aria-label': 'Назад' },
        icons.back()),
      title
        ? h('div', { style: { minWidth: 0 } },
            h('div', {
              style: {
                fontSize: '20px', fontWeight: '800', color: 'var(--rm-green-dark)',
                overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
              },
            }, title),
            subtitle
              ? h('div', {
                  style: {
                    fontSize: '13px', color: 'var(--rm-text-muted)',
                    overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                  },
                }, subtitle)
              : null,
          )
        : null,
    ),
    right,
  );
}

/** Sticky action bar at the bottom of form screens. */
export function footerBar(...children) {
  return h('div', {
    style: {
      position: 'fixed', left: 0, right: 0, bottom: 0, background: '#FFFFFF',
      borderTop: '1px solid var(--rm-border-soft)',
      padding: '14px 20px calc(30px + var(--rm-safe-bottom))',
      display: 'flex', gap: '10px', zIndex: '30',
    },
  }, children);
}

// ------------------------------------------------------------------ tab bar

export function tabBar(active) {
  const item = (key, label, iconNode, path) =>
    h('button', {
      class: `rm-tab${active === key ? ' rm-tab--active' : ''}`,
      onClick: () => { haptic('selection'); navigate(path); },
    }, iconNode, h('div.rm-tab__label', null, label));

  const aiFab = h('div.rm-tab__fab', null, aiAvatar(28, 'transparent', active === 'ai' ? '#027C41' : '#0A9A54'));
  // The FAB itself is the white "face"; recreate the design's exact inner shape.
  clear(aiFab).appendChild(svg(`
    <div style="width:28px;height:22px;border-radius:8px;background:#FFFFFF;display:flex;align-items:center;justify-content:center;gap:5px">
      <div style="width:5px;height:5px;border-radius:50%;background:${active === 'ai' ? '#027C41' : '#0A9A54'}"></div>
      <div style="width:5px;height:5px;border-radius:50%;background:${active === 'ai' ? '#027C41' : '#0A9A54'}"></div>
    </div>`));

  return h('div.rm-tabbar', null,
    item('library', 'Главная', icons.home(24, active === 'library' ? '#027C41' : '#A7ADB5'), '/'),
    h('button', {
      class: `rm-tab${active === 'ai' ? ' rm-tab--active' : ''}`,
      onClick: () => { haptic('selection'); navigate('/ai'); },
    }, aiFab, h('div.rm-tab__label', null, 'Помощник')),
    item('profile', 'Профиль', icons.user(24, active === 'profile' ? '#027C41' : '#A7ADB5'), '/profile'),
  );
}

// ------------------------------------------------------------------ overlays

/**
 * Bottom sheet, matching the canvas: grabber, title, content, dimmed backdrop.
 * @returns {{ close: () => void, element: HTMLElement }}
 */
export function openSheet({ title, subtitle, onClose, dismissible = true }, ...content) {
  const root = overlayRoot();
  const backdrop = h('div.rm-backdrop');
  const sheet = h('div.rm-sheet', null,
    h('div.rm-sheet__grabber'),
    title
      ? h('div', { style: { display: 'flex', alignItems: 'center', justifyContent: 'space-between' } },
          h('div', null,
            h('div.rm-sheet__title', null, title),
            subtitle
              ? h('div', { style: { marginTop: '4px', fontSize: '14px', color: 'var(--rm-text-muted)' } }, subtitle)
              : null,
          ),
          dismissible
            ? h('button', {
                style: {
                  width: '32px', height: '32px', borderRadius: '50%', background: 'var(--rm-surface-grey)',
                  border: 'none', display: 'flex', alignItems: 'center', justifyContent: 'center',
                },
                onClick: () => close(),
                'aria-label': 'Закрыть',
              }, icons.close())
            : null,
        )
      : null,
  );
  append(sheet, content);

  let closed = false;
  function close() {
    if (closed) return;
    closed = true;
    unregisterOverlay(handle);
    backdrop.remove();
    sheet.remove();
    document.body.style.overflow = '';
    if (onClose) onClose();
  }

  const handle = { close, element: sheet };
  registerOverlay(handle);

  if (dismissible) backdrop.addEventListener('click', close);
  document.body.style.overflow = 'hidden';
  root.append(backdrop, sheet);
  return handle;
}

/** Action sheet (the "…" menu on entries, the "+" chooser inside a book). */
export function openActionSheet({ title, subtitle, actions, cancelLabel = 'Отмена' }) {
  const sheet = openSheet({ title, subtitle },
    h('div', { style: { marginTop: title ? '18px' : '4px', display: 'flex', flexDirection: 'column', gap: '10px' } },
      ...actions.map((action) =>
        h('button', {
          style: {
            width: '100%', minHeight: '58px', borderRadius: '18px',
            background: action.danger ? 'var(--rm-danger-soft)' : 'var(--rm-surface-tint)',
            border: `1px solid ${action.danger ? '#F6DADA' : 'var(--rm-border-soft)'}`,
            display: 'flex', alignItems: 'center', gap: '12px', padding: '12px 16px',
            fontSize: '16px', textAlign: 'left',
            color: action.danger ? 'var(--rm-danger)' : 'var(--rm-text)',
          },
          onClick: () => { haptic('light'); sheet.close(); action.onSelect(); },
        },
          action.icon || null,
          h('div', { style: { flex: '1' } },
            h('div', null, action.label),
            action.description
              ? h('div', { style: { marginTop: '2px', fontSize: '13px', color: 'var(--rm-text-muted)' } },
                  action.description)
              : null,
          ),
        ),
      ),
      h('button.rm-btn.rm-btn--quiet', { onClick: () => sheet.close() }, cancelLabel),
    ),
  );
  return sheet;
}

/** Destructive confirmation, matching screens 16 and 38. */
export function confirmDialog({ title, text, confirmLabel, cancelLabel = 'Отмена', onConfirm }) {
  return new Promise((resolve) => {
    let confirmed = false;
    const sheet = openSheet({ onClose: () => resolve(confirmed) },
      h('div', { style: { paddingTop: '4px', textAlign: 'center' } },
        h('div', {
          style: {
            width: '64px', height: '64px', margin: '0 auto', borderRadius: '22px',
            background: 'var(--rm-danger-soft)', display: 'flex', alignItems: 'center',
            justifyContent: 'center',
          },
        }, icons.warning(28)),
        h('div', {
          style: {
            marginTop: '18px', fontSize: '22px', fontWeight: '800',
            color: 'var(--rm-green-dark)', lineHeight: '1.2',
          },
        }, title),
        h('div', {
          style: {
            marginTop: '10px', fontSize: '15px', lineHeight: '1.5',
            color: 'var(--rm-text-secondary)',
          },
        }, text),
        h('div', { style: { marginTop: '22px', display: 'flex', flexDirection: 'column', gap: '10px' } },
          h('button.rm-btn.rm-btn--danger', {
            onClick: async () => {
              confirmed = true;
              haptic('warning');
              sheet.close();
              if (onConfirm) await onConfirm();
            },
          }, confirmLabel),
          h('button.rm-btn.rm-btn--quiet', { onClick: () => sheet.close() }, cancelLabel),
        ),
      ),
    );
  });
}

// ------------------------------------------------------------------ toasts

export function toast(message, { type = 'success', timeout = 2600 } = {}) {
  const root = document.getElementById('toasts');
  const node = h('div', { class: `rm-toast${type === 'error' ? ' rm-toast--error' : ''}` },
    type === 'success' ? icons.check(16, '#FFFFFF', 2.8) : icons.warning(16, '#FFFFFF'),
    h('span', null, message),
  );
  root.appendChild(node);
  haptic(type === 'error' ? 'error' : 'success');
  setTimeout(() => {
    node.style.opacity = '0';
    node.style.transition = 'opacity .2s';
    setTimeout(() => node.remove(), 220);
  }, timeout);
  return node;
}

/** Logs the real cause behind a state we already showed the user. */
export function logError(context, error) {
  if (error instanceof ApiError) {
    console.warn(`[remarka] ${context}: ${error.code} (${error.status}) ${error.message}`);
  } else {
    console.error(`[remarka] ${context}:`, error);
  }
}

/** Turns any thrown value into a user-facing toast; re-raises nothing. */
export function toastError(error) {
  const message = error instanceof ApiError ? errorMessage(error) : 'Что-то пошло не так';
  toast(message, { type: 'error' });
  if (!(error instanceof ApiError)) console.error(error);
}

// ------------------------------------------------------------------ states

export function skeletonBlock(height, radius = '14px', extra = {}) {
  return h('div.rm-skeleton', { style: { height, borderRadius: radius, ...extra } });
}

/** Library loading state, mirroring screen 09. */
export function librarySkeleton() {
  const card = () =>
    h('div', {
      style: {
        background: '#FFFFFF', borderRadius: '20px', boxShadow: 'var(--rm-shadow-card)', padding: '10px',
      },
    },
      skeletonBlock('0', '14px', { aspectRatio: '1 / 1.18' }),
      skeletonBlock('13px', '7px', { marginTop: '12px', width: '80%' }),
      skeletonBlock('11px', '6px', { marginTop: '8px', width: '50%' }),
    );
  return h('div', {
    style: { marginTop: '16px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px' },
  }, card(), card(), card(), card());
}

export function emptyState({ icon, title, text, actionLabel, onAction }) {
  return h('div.rm-empty', null,
    icon
      ? h('div', {
          style: {
            width: '72px', height: '72px', margin: '0 auto', borderRadius: '24px',
            background: 'var(--rm-surface-soft)', display: 'flex', alignItems: 'center',
            justifyContent: 'center',
          },
        }, icon)
      : null,
    h('div.rm-empty__title', null, title),
    text ? h('div.rm-empty__text', null, text) : null,
    actionLabel
      ? h('button.rm-btn', {
          style: { marginTop: '22px', maxWidth: '260px', marginLeft: 'auto', marginRight: 'auto' },
          onClick: onAction,
        }, actionLabel)
      : null,
  );
}

/** Error state with a retry, mirroring screens 02 and 10. */
export function errorState({ title = 'Не удалось загрузить', text = 'Проверьте соединение и попробуйте снова', onRetry }) {
  return h('div.rm-empty', null,
    h('div', {
      style: {
        width: '72px', height: '72px', margin: '0 auto', borderRadius: '24px',
        background: 'var(--rm-danger-soft)', display: 'flex', alignItems: 'center', justifyContent: 'center',
      },
    }, icons.warning(30)),
    h('div.rm-empty__title', null, title),
    h('div.rm-empty__text', null, text),
    onRetry
      ? h('button.rm-btn', {
          style: { marginTop: '22px', maxWidth: '220px', marginLeft: 'auto', marginRight: 'auto' },
          onClick: onRetry,
        }, 'Повторить')
      : null,
  );
}

// ------------------------------------------------------------------ book cover

/** Deterministic placeholder palettes, taken from the covers drawn in the canvas. */
const COVER_PALETTES = [
  { bg: '#E9F2E4', fg: '#1F6B3B' },
  { bg: '#F5EFE2', fg: '#8A6A32' },
  { bg: '#F2E6D2', fg: '#8A6A32' },
  { bg: '#14532D', fg: '#E2C169' },
  { bg: '#EAF4EC', fg: '#14532D' },
  { bg: '#F3F6F4', fg: '#4A5158' },
];

export function coverPalette(title = '') {
  let hash = 0;
  for (const char of String(title)) hash = (hash * 31 + char.codePointAt(0)) >>> 0;
  return COVER_PALETTES[hash % COVER_PALETTES.length];
}

/**
 * Book cover: the real image when we have one, otherwise the canvas' typographic
 * placeholder in a deterministic palette.
 */
export function bookCover(book, { width, height, aspect, radius = '14px', fontSize = 15 } = {}) {
  const palette = coverPalette(book?.title || '');
  const style = {
    position: 'relative',
    borderRadius: radius,
    background: palette.bg,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '10px',
    overflow: 'hidden',
    flex: width ? '0 0 auto' : undefined,
  };
  if (width) style.width = width;
  if (height) style.height = height;
  if (aspect) style.aspectRatio = aspect;

  const node = h('div', { style });
  if (book?.cover_url) {
    const img = h('img', {
      src: book.cover_url,
      alt: book.title || '',
      loading: 'lazy',
      style: { width: '100%', height: '100%', objectFit: 'cover', display: 'block' },
    });
    // A dead third-party URL must not leave an empty box.
    img.addEventListener('error', () => { img.remove(); node.appendChild(coverText(book, palette, fontSize)); });
    node.style.padding = '0';
    node.appendChild(img);
  } else {
    node.appendChild(coverText(book, palette, fontSize));
  }
  return node;
}

function coverText(book, palette, fontSize) {
  return h('div', {
    style: {
      font: `700 ${fontSize}px/1.25 var(--rm-font-serif)`,
      color: palette.fg,
      textAlign: 'center',
      textTransform: 'uppercase',
      letterSpacing: '.02em',
      padding: '4px',
    },
  }, book?.title || 'Без названия');
}

// ------------------------------------------------------------------ misc

export function chip(label, { active = false, dashed = false, onClick } = {}) {
  return h('button', {
    class: `rm-chip${active ? ' rm-chip--active' : ''}${dashed ? ' rm-chip--dashed' : ''}`,
    onClick: onClick ? () => { haptic('selection'); onClick(); } : undefined,
  }, label);
}

export function tagPill(name, { onRemove, filled = false } = {}) {
  return h('div', {
    style: {
      height: onRemove ? '34px' : '26px',
      padding: onRemove ? '0 14px' : '0 11px',
      borderRadius: onRemove ? '17px' : '13px',
      border: filled ? 'none' : '1px solid var(--rm-border-green)',
      background: filled ? 'var(--rm-surface-mint)' : '#FFFFFF',
      fontSize: onRemove ? '13px' : '12px',
      color: 'var(--rm-green-dark)',
      display: 'flex',
      alignItems: 'center',
      gap: '7px',
      whiteSpace: 'nowrap',
    },
  },
    name,
    onRemove
      ? h('button', {
          style: { border: 'none', background: 'none', padding: '0', display: 'flex', alignItems: 'center' },
          onClick: onRemove,
          'aria-label': `Убрать тег ${name}`,
        }, icons.close(10, '#14532D'))
      : null,
  );
}

/** A row in the settings/profile list. */
export function listRow({ icon, label, value, onClick, danger = false, last = false, iconBg }) {
  return h('button', {
    style: {
      width: '100%', minHeight: '58px', display: 'flex', alignItems: 'center', gap: '14px',
      padding: '0 16px', border: 'none', background: 'transparent', textAlign: 'left',
      borderBottom: last ? 'none' : '1px solid var(--rm-surface-grey)',
    },
    onClick: onClick ? () => { haptic('light'); onClick(); } : undefined,
  },
    icon
      ? h('div', {
          style: {
            width: '34px', height: '34px', borderRadius: '12px',
            background: iconBg || 'var(--rm-surface-grey)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', flex: '0 0 auto',
          },
        }, icon)
      : null,
    h('div', {
      style: { flex: '1', fontSize: '16px', color: danger ? 'var(--rm-danger)' : 'var(--rm-text)' },
    }, label),
    value ? h('div', { style: { fontSize: '15px', color: 'var(--rm-text-muted)' } }, value) : null,
    onClick ? icons.chevron() : null,
  );
}

export function switchControl(checked, onChange) {
  const knob = h('div', {
    style: {
      width: '27px', height: '27px', borderRadius: '50%', background: '#FFFFFF',
      boxShadow: '0 2px 5px rgba(0,0,0,.15)',
    },
  });
  const track = h('button', {
    style: {
      width: '51px', height: '31px', borderRadius: '16px', border: 'none',
      background: checked ? 'var(--rm-green)' : '#E1E6E2', padding: '2px',
      display: 'flex', justifyContent: checked ? 'flex-end' : 'flex-start',
      transition: 'background .18s',
    },
    onClick: () => { haptic('selection'); onChange(!checked); },
    role: 'switch',
    'aria-checked': String(checked),
  }, knob);
  return track;
}

/** Wires Telegram's native BackButton to a screen while it is mounted. */
export function useTelegramBack(fallback = '/') {
  if (currentPath() === '/') return () => {};
  return showBackButton(() => back(fallback));
}

export function formatDate(value) {
  if (!value) return '';
  const date = new Date(value);
  const now = new Date();
  const sameDay = date.toDateString() === now.toDateString();
  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  if (sameDay) {
    return `Сегодня, ${date.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })}`;
  }
  if (date.toDateString() === yesterday.toDateString()) return 'Вчера';
  return date.toLocaleDateString('ru-RU', {
    day: 'numeric',
    month: 'long',
    year: date.getFullYear() === now.getFullYear() ? undefined : 'numeric',
  });
}

export function formatShortDate(value) {
  if (!value) return '';
  return new Date(value).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short', year: 'numeric' });
}

export function plural(count, one, few, many) {
  const mod10 = count % 10;
  const mod100 = count % 100;
  if (mod10 === 1 && mod100 !== 11) return `${count} ${one}`;
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 10 || mod100 >= 20)) return `${count} ${few}`;
  return `${count} ${many}`;
}
