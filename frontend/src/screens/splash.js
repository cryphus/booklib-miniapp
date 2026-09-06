/** Screen 01 — Splash, shown while the session is being established. */

import { h, svg } from '../ui/dom.js';

export function splashScreen() {
  return h('div', {
    style: {
      minHeight: '100dvh', display: 'flex', flexDirection: 'column', alignItems: 'center',
      justifyContent: 'center', gap: '24px', paddingBottom: '80px', background: '#FFFFFF',
    },
  },
    h('div', {
      style: {
        width: '92px', height: '92px', borderRadius: '28px', background: 'var(--rm-green)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        boxShadow: '0 14px 30px rgba(2,124,65,.28)',
      },
    },
      svg(`<svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#FFFFFF" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M5 5a2 2 0 0 1 2-2h12v18H7a2 2 0 0 1-2-2z"></path><path d="M9 3v18"></path></svg>`),
    ),
    h('div', { style: { textAlign: 'center' } },
      h('div', {
        style: {
          fontSize: '30px', fontWeight: '800', color: 'var(--rm-green-dark)', letterSpacing: '-.02em',
        },
      }, 'Remarka'),
      h('div', { style: { marginTop: '6px', fontSize: '15px', color: 'var(--rm-text-muted)' } },
        'Твоя библиотека мыслей'),
    ),
    h('div', {
      style: { display: 'flex', alignItems: 'center', gap: '10px', fontSize: '14px', color: 'var(--rm-text-muted)' },
    },
      h('div.rm-spinner.rm-spinner--green', { style: { width: '16px', height: '16px' } }),
      'Вход через Telegram',
    ),
  );
}
