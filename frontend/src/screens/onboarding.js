/** Screens 03–05 — three-step onboarding, finished by flagging the account. */

import { api } from '../api/client.js';
import { haptic } from '../api/telegram.js';
import { navigate } from '../router.js';
import { invalidate, keys, setState } from '../store.js';
import { aiAvatar, icons, quoteGlyph } from '../ui/icons.js';
import { h, fill } from '../ui/dom.js';
import { toastError } from '../ui/components.js';

const STEPS = [
  {
    title: 'Сохраняй важное из книг',
    text: 'Книги, цитаты и собственные мысли — в одном месте.',
    art: () =>
      h('div', { style: { display: 'flex', gap: '12px', alignItems: 'flex-end', justifyContent: 'center' } },
        h('div', {
          style: {
            width: '96px', height: '124px', borderRadius: '16px', background: '#E9F2E4',
            display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '10px',
            font: '700 12px/1.3 var(--rm-font-serif)', color: '#1F6B3B', textAlign: 'center',
            textTransform: 'uppercase',
          },
        }, 'книги · цитаты'),
        h('div', {
          style: {
            width: '110px', borderRadius: '18px', background: '#FFFFFF',
            boxShadow: 'var(--rm-shadow-card)', padding: '12px', display: 'flex',
            flexDirection: 'column', gap: '8px',
          },
        },
          quoteGlyph(26),
          h('div', { style: { fontSize: '12px', lineHeight: '1.4', color: 'var(--rm-text-secondary)' } },
            'заметки'),
        ),
      ),
  },
  {
    title: 'Находи нужную мысль',
    text: 'Быстрый поиск по всей своей библиотеке.',
    art: () =>
      h('div', {
        style: {
          width: '260px', margin: '0 auto', borderRadius: '20px', background: '#FFFFFF',
          boxShadow: 'var(--rm-shadow-card-strong)', padding: '16px', display: 'flex',
          flexDirection: 'column', gap: '12px',
        },
      },
        h('div', {
          style: {
            height: '46px', borderRadius: '16px', border: '1.5px solid var(--rm-green)',
            display: 'flex', alignItems: 'center', gap: '10px', padding: '0 14px',
          },
        }, icons.search(18), h('div', { style: { fontSize: '15px', color: 'var(--rm-text)' } }, 'капитал')),
        h('div.rm-skeleton', { style: { height: '12px', width: '85%' } }),
        h('div.rm-skeleton', { style: { height: '12px', width: '65%' } }),
      ),
  },
  {
    title: 'Спрашивай Remarka AI',
    text: 'AI отвечает только по вашим материалам и показывает источники.',
    art: () =>
      h('div', { style: { width: '272px', margin: '0 auto', display: 'flex', gap: '10px' } },
        aiAvatar(34),
        h('div', { style: { flex: '1' } },
          h('div', {
            style: {
              background: '#FFFFFF', borderRadius: '20px', boxShadow: 'var(--rm-shadow-card-strong)',
              padding: '14px', fontSize: '14px', lineHeight: '1.45', color: 'var(--rm-text)',
            },
          }, 'Нашёл 4 записи по теме «управление капиталом».'),
          h('div', {
            style: {
              marginTop: '10px', display: 'flex', gap: '10px', alignItems: 'center',
              background: '#FFFFFF', borderRadius: '16px', boxShadow: 'var(--rm-shadow-card)', padding: '8px',
            },
          },
            h('div', {
              style: {
                width: '40px', height: '52px', borderRadius: '8px', background: '#E9F2E4',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                font: '700 7px/1.2 var(--rm-font-serif)', color: '#1F6B3B', textAlign: 'center',
                textTransform: 'uppercase', padding: '3px',
              },
            }, 'обложка'),
            h('div', { style: { flex: '1' } },
              h('div.rm-skeleton', { style: { height: '10px', width: '80%' } }),
              h('div.rm-skeleton', { style: { height: '9px', width: '55%', marginTop: '6px' } }),
            ),
          ),
        ),
      ),
  },
];

export function onboardingScreen({ query: search }) {
  let step = Math.min(Math.max(parseInt(search.get('step') || '1', 10), 1), STEPS.length) - 1;

  const container = h('div', {
    style: {
      minHeight: '100dvh', display: 'flex', flexDirection: 'column',
      padding: 'calc(var(--rm-safe-top) + 16px) 20px calc(var(--rm-safe-bottom) + 30px)',
    },
  });

  async function finish() {
    try {
      const me = await api.updateMe({ onboarding_completed: true });
      setState({ me });
      invalidate(keys.me);
    } catch (error) {
      // Onboarding must never trap the user: log it and continue into the app.
      toastError(error);
    }
    navigate('/', { replace: true });
  }

  function render() {
    const current = STEPS[step];
    const isLast = step === STEPS.length - 1;

    fill(container, 
      h('div', { style: { display: 'flex', justifyContent: 'flex-end' } },
        h('button', {
          style: { border: 'none', background: 'none', fontSize: '15px', color: 'var(--rm-text-muted)' },
          onClick: finish,
        }, 'Пропустить'),
      ),
      h('div', {
        style: {
          flex: '1', display: 'flex', flexDirection: 'column', alignItems: 'center',
          justifyContent: 'center', gap: '32px', textAlign: 'center',
        },
      },
        current.art(),
        h('div', null,
          h('div', {
            style: {
              fontSize: '28px', fontWeight: '800', color: 'var(--rm-green-dark)',
              letterSpacing: '-.02em', lineHeight: '1.15',
            },
          }, current.title),
          h('div', {
            style: {
              marginTop: '10px', fontSize: '16px', lineHeight: '1.5',
              color: 'var(--rm-text-secondary)', maxWidth: '300px', margin: '10px auto 0',
            },
          }, current.text),
        ),
      ),
      h('div', { style: { display: 'flex', justifyContent: 'center', gap: '7px', marginBottom: '22px' } },
        ...STEPS.map((_s, index) =>
          h('div', {
            style: {
              width: index === step ? '22px' : '7px', height: '7px', borderRadius: '4px',
              background: index === step ? 'var(--rm-green)' : '#DCE7DF', transition: 'width .2s',
            },
          }),
        ),
      ),
      h('button.rm-btn', {
        onClick: () => {
          haptic('light');
          if (isLast) finish();
          else { step += 1; render(); }
        },
      }, isLast ? 'Начать' : 'Далее'),
    );
  }

  render();
  return container;
}
