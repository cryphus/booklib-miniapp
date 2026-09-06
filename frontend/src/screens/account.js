/**
 * Screens 37–38 — account: the Telegram identity, the future login methods, and
 * account deletion, which really deletes everything on the backend.
 */

import { api } from '../api/client.js';
import { navigate } from '../router.js';
import { getState, invalidateAll, keys, query } from '../store.js';
import { closeApp } from '../api/telegram.js';
import { icons } from '../ui/icons.js';
import { h, fill } from '../ui/dom.js';
import {
  backHeader,
  confirmDialog,
  errorState,
  screen,
  skeletonBlock,
  toastError,
  useTelegramBack,
  logError,
} from '../ui/components.js';

const FUTURE_PROVIDERS = ['Google', 'Apple', 'Email'];

export function accountScreen({ query: search }) {
  const body = h('div');
  const view = screen({ header: backHeader('Аккаунт') }, body);
  view.__cleanup = useTelegramBack('/settings');

  load(search.get('delete') === '1');
  return view;

  async function load(openDelete) {
    fill(body, skeletonBlock('120px', '22px', { marginTop: '18px' }));
    try {
      const me = getState().me || (await query(keys.me, () => api.getMe(), { ttl: 30_000 }));
      render(me);
      if (openDelete) confirmDeletion();
    } catch (error) {
      fill(body, errorState({ title: 'Не удалось загрузить аккаунт', onRetry: () => load(false) }));
      logError('account', error);
    }
  }

  function render(me) {
    const profile = me.profile || {};
    const fullName = [profile.first_name, profile.last_name].filter(Boolean).join(' ') || 'Читатель';
    const initials = fullName.split(' ').slice(0, 2).map((p) => p[0]).join('').toUpperCase();

    fill(body, 
      h('div', {
        style: {
          marginTop: '18px', borderRadius: '22px', background: 'var(--rm-surface-soft)',
          padding: '18px', display: 'flex', alignItems: 'center', gap: '16px',
        },
      },
        profile.avatar_url
          ? h('img', {
              src: profile.avatar_url,
              alt: '',
              style: { width: '58px', height: '58px', borderRadius: '50%', objectFit: 'cover' },
            })
          : h('div', {
              style: {
                width: '58px', height: '58px', flex: '0 0 auto', borderRadius: '50%',
                background: '#DCEAE0', display: 'flex', alignItems: 'center',
                justifyContent: 'center', fontSize: '20px', fontWeight: '700',
                color: 'var(--rm-green-dark)',
              },
            }, initials),
        h('div', { style: { flex: '1', minWidth: 0 } },
          h('div', { style: { fontSize: '18px', fontWeight: '800' } }, fullName),
          profile.username
            ? h('div', { style: { marginTop: '2px', fontSize: '14px', color: 'var(--rm-text-secondary)' } },
                `@${profile.username}`)
            : null,
        ),
        h('div', {
          style: {
            height: '26px', padding: '0 11px', borderRadius: '13px', background: '#FFFFFF',
            fontSize: '12px', fontWeight: '600', color: 'var(--rm-green)',
            display: 'flex', alignItems: 'center', gap: '6px',
          },
        },
          h('span', { style: { width: '6px', height: '6px', borderRadius: '50%', background: 'var(--rm-green)' } }),
          'Подключено',
        ),
      ),

      h('div', {
        style: {
          marginTop: '14px', fontSize: '14px', lineHeight: '1.5', color: 'var(--rm-text-secondary)',
          padding: '0 4px',
        },
      }, 'Ваша библиотека хранится в аккаунте Remarka и не зависит от устройства.'),

      h('div.rm-section-label', { style: { marginTop: '24px' } }, 'Другие способы входа'),
      h('div', {
        style: {
          marginTop: '10px', background: '#FFFFFF', borderRadius: '20px',
          boxShadow: 'var(--rm-shadow-card)', overflow: 'hidden',
        },
      },
        // TODO(identities): wire Google / Apple / email to /auth once those providers exist.
        ...FUTURE_PROVIDERS.map((name, index) =>
          h('div', {
            style: {
              height: '56px', display: 'flex', alignItems: 'center', padding: '0 16px',
              fontSize: '16px', color: 'var(--rm-text)',
              borderBottom: index === FUTURE_PROVIDERS.length - 1 ? 'none' : '1px solid var(--rm-surface-grey)',
            },
          },
            h('div', { style: { flex: '1' } }, name),
            h('div', {
              style: {
                height: '24px', padding: '0 10px', borderRadius: '12px',
                background: 'var(--rm-surface-grey)', fontSize: '12px',
                color: 'var(--rm-text-muted)', display: 'flex', alignItems: 'center',
              },
            }, 'Позже'),
          ),
        ),
      ),

      h('button', {
        style: {
          marginTop: '28px', width: '100%', height: '54px', borderRadius: '18px',
          border: '1px solid #F3DADA', background: 'var(--rm-danger-soft)',
          color: 'var(--rm-danger)', fontSize: '16px', fontWeight: '600',
        },
        onClick: confirmDeletion,
      }, 'Удалить аккаунт'),
      h('div', { style: { height: '30px' } }),
    );
  }

  function confirmDeletion() {
    confirmDialog({
      title: 'Удалить аккаунт?',
      text: 'Все книги, цитаты, заметки и история AI будут удалены без возможности восстановления.',
      confirmLabel: 'Удалить аккаунт',
      onConfirm: async () => {
        try {
          await api.deleteAccount();
          api.clearToken();
          invalidateAll();
          showFarewell();
        } catch (error) {
          toastError(error);
        }
      },
    });
  }

  function showFarewell() {
    fill(document.getElementById('app'), 
      h('div', {
        style: {
          minHeight: '100dvh', display: 'flex', flexDirection: 'column', alignItems: 'center',
          justifyContent: 'center', gap: '18px', padding: '0 28px', textAlign: 'center',
        },
      },
        h('div', {
          style: {
            width: '72px', height: '72px', borderRadius: '26px', background: 'var(--rm-surface-soft)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          },
        }, icons.check(32, '#027C41', 2.8)),
        h('div', { style: { fontSize: '22px', fontWeight: '800', color: 'var(--rm-green-dark)' } },
          'Аккаунт удалён'),
        h('div', { style: { fontSize: '15px', lineHeight: '1.5', color: 'var(--rm-text-secondary)' } },
          'Все ваши книги, цитаты и заметки удалены. Спасибо, что были с Remarka.'),
        h('button.rm-btn', { style: { maxWidth: '240px', marginTop: '10px' }, onClick: closeApp },
          'Закрыть'),
      ),
    );
  }
}

export { navigate };
