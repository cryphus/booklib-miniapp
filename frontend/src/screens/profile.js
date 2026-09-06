/** Screen 31 — profile: Telegram identity, counters, plan with AI usage, menu. */

import { api } from '../api/client.js';
import { navigate } from '../router.js';
import { getState, keys, query, setState } from '../store.js';
import { icons } from '../ui/icons.js';
import { h, fill } from '../ui/dom.js';
import {
  errorState,
  listRow,
  pageHeader,
  screen,
  skeletonBlock,
  logError,
} from '../ui/components.js';

export function profileScreen() {
  const body = h('div');
  const view = screen({ tab: 'profile' }, pageHeader('Профиль'), body);

  load();
  return view;

  async function load() {
    fill(body, 
      skeletonBlock('100px', '22px', { marginTop: '16px' }),
      skeletonBlock('78px', '18px', { marginTop: '14px' }),
      skeletonBlock('190px', '22px', { marginTop: '14px' }),
    );
    try {
      const [me, stats, billing] = await Promise.all([
        query(keys.me, () => api.getMe(), { ttl: 20_000, force: true }),
        query(keys.stats, () => api.getStats(), { ttl: 20_000, force: true }),
        query(keys.billing, () => api.getBillingStatus(), { ttl: 20_000, force: true }),
      ]);
      setState({ me, billing, aiUsage: me.ai_usage });
      render(me, stats, billing);
    } catch (error) {
      fill(body, errorState({ title: 'Не удалось загрузить профиль', onRetry: load }));
      logError('profile', error);
    }
  }

  function render(me, stats, billing) {
    const profile = me.profile || {};
    const fullName = [profile.first_name, profile.last_name].filter(Boolean).join(' ') || 'Читатель';
    const initials = fullName
      .split(' ')
      .slice(0, 2)
      .map((part) => part[0])
      .join('')
      .toUpperCase();

    const usedRatio = billing.ai_limit ? Math.min(billing.ai_used / billing.ai_limit, 1) : 0;

    fill(body, 
      // identity card
      h('div', {
        style: {
          marginTop: '16px', borderRadius: '22px', background: 'var(--rm-surface-soft)',
          padding: '18px', display: 'flex', alignItems: 'center', gap: '16px',
        },
      },
        profile.avatar_url
          ? h('img', {
              src: profile.avatar_url,
              alt: '',
              style: {
                width: '64px', height: '64px', borderRadius: '50%', objectFit: 'cover',
                border: '2px solid #FFFFFF', flex: '0 0 auto',
              },
            })
          : h('div', {
              style: {
                width: '64px', height: '64px', flex: '0 0 auto', borderRadius: '50%',
                background: '#DCEAE0', border: '2px solid #FFFFFF', display: 'flex',
                alignItems: 'center', justifyContent: 'center', fontSize: '22px',
                fontWeight: '700', color: 'var(--rm-green-dark)',
              },
            }, initials),
        h('div', { style: { flex: '1', minWidth: 0 } },
          h('div', { style: { fontSize: '20px', fontWeight: '800' } }, fullName),
          profile.username
            ? h('div', { style: { marginTop: '3px', fontSize: '14px', color: 'var(--rm-text-secondary)' } },
                `@${profile.username}`)
            : null,
          h('div', {
            style: {
              marginTop: '8px', display: 'inline-flex', alignItems: 'center', gap: '6px',
              height: '26px', padding: '0 10px', borderRadius: '13px', background: '#FFFFFF',
              fontSize: '12px', fontWeight: '600', color: 'var(--rm-green)',
            },
          },
            h('span', { style: { width: '6px', height: '6px', borderRadius: '50%', background: 'var(--rm-green)' } }),
            'Telegram подключён',
          ),
        ),
      ),

      // counters
      h('div', { style: { marginTop: '14px', display: 'flex', gap: '10px' } },
        counter(stats.books_count, 'книг'),
        counter(stats.quotes_count, 'цитаты'),
        counter(stats.notes_count, 'заметки'),
      ),

      // plan card
      h('div', {
        style: {
          marginTop: '14px', background: '#FFFFFF', borderRadius: '22px',
          boxShadow: 'var(--rm-shadow-card)', padding: '18px',
        },
      },
        h('div', { style: { display: 'flex', alignItems: 'center', justifyContent: 'space-between' } },
          h('div', { style: { fontSize: '17px', fontWeight: '800' } },
            billing.is_premium ? 'Тариф Premium' : 'Тариф Free'),
          h('div', {
            style: {
              height: '26px', padding: '0 11px', borderRadius: '13px',
              background: 'var(--rm-surface-soft)', fontSize: '12px', fontWeight: '600',
              color: 'var(--rm-green)', display: 'flex', alignItems: 'center',
            },
          }, `${billing.ai_used} / ${billing.ai_limit}`),
        ),
        h('div', { style: { marginTop: '10px', fontSize: '14px', color: 'var(--rm-text-secondary)' } },
          `${billing.ai_used} из ${billing.ai_limit} AI-запросов использовано`),
        h('div', {
          style: {
            marginTop: '12px', height: '8px', borderRadius: '4px', background: '#EDF2EE', overflow: 'hidden',
          },
        },
          h('div', {
            style: {
              width: `${Math.round(usedRatio * 100)}%`, height: '100%', borderRadius: '4px',
              background: usedRatio >= 1 ? 'var(--rm-danger)' : 'var(--rm-green)',
            },
          }),
        ),
        h('button.rm-btn', {
          style: { marginTop: '16px', height: '52px', borderRadius: '17px' },
          onClick: () => navigate('/premium'),
        }, billing.is_premium ? 'Управление Premium' : 'Получить Premium'),
      ),

      // menu
      h('div', {
        style: {
          marginTop: '14px', background: '#FFFFFF', borderRadius: '22px',
          boxShadow: 'var(--rm-shadow-card)', overflow: 'hidden',
        },
      },
        listRow({
          icon: icons.star(18),
          iconBg: 'var(--rm-surface-soft)',
          label: 'Premium',
          onClick: () => navigate('/premium'),
        }),
        listRow({ icon: icons.settings(), label: 'Настройки', onClick: () => navigate('/settings') }),
        listRow({ icon: icons.support(), label: 'Поддержка', onClick: () => navigate('/support') }),
        listRow({
          icon: icons.info(),
          label: 'О приложении',
          onClick: () => navigate('/legal/about'),
          last: true,
        }),
      ),
      h('div', { style: { height: '20px' } }),
    );
  }

  function counter(value, label) {
    return h('div', {
      style: {
        flex: '1', background: '#FFFFFF', borderRadius: '18px', boxShadow: 'var(--rm-shadow-card)',
        padding: '14px 12px', textAlign: 'center',
      },
    },
      h('div', { style: { fontSize: '24px', fontWeight: '800', color: 'var(--rm-green-dark)' } }, String(value)),
      h('div', { style: { marginTop: '2px', fontSize: '13px', color: 'var(--rm-text-muted)' } }, label),
    );
  }
}

export { getState };
