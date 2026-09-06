/**
 * Screens 32–35 — Premium.
 *
 * The full Telegram Stars flow: the backend creates the invoice, Telegram shows the
 * payment UI, the webhook activates the subscription, and this screen polls the
 * payment until the backend confirms it. Available providers come from the backend,
 * never from a hardcoded list.
 */

import { api } from '../api/client.js';
import { haptic, isTelegram, openInvoice } from '../api/telegram.js';
import { navigate } from '../router.js';
import { invalidate, keys, query, setState } from '../store.js';
import { icons } from '../ui/icons.js';
import { h, fill } from '../ui/dom.js';
import {
  backHeader,
  errorState,
  formatShortDate,
  listRow,
  openSheet,
  screen,
  skeletonBlock,
  toastError,
  useTelegramBack,
  logError,
} from '../ui/components.js';

const BENEFITS = [
  'Больше AI-запросов',
  'AI по всей библиотеке',
  'Расширенные возможности Remarka AI',
  'Новые Premium-функции в будущем',
];

const PROVIDER_LABELS = {
  telegram_stars: 'Telegram Stars',
  yookassa: 'Банковская карта (ЮKassa)',
  platega: 'Platega',
  cryptobot: 'Криптовалюта (CryptoBot)',
};

export function premiumScreen() {
  const body = h('div');
  const view = screen({ header: backHeader(null) }, body);
  view.__cleanup = useTelegramBack('/profile');

  load();
  return view;

  async function load() {
    fill(body, 
      skeletonBlock('60px', '20px', { marginTop: '16px' }),
      skeletonBlock('90px', '20px', { marginTop: '16px' }),
      skeletonBlock('200px', '20px', { marginTop: '16px' }),
    );
    try {
      const [billing, providers] = await Promise.all([
        query(keys.billing, () => api.getBillingStatus(), { ttl: 5_000, force: true }),
        query(keys.providers, () => api.getPaymentProviders(), { ttl: 300_000 }),
      ]);
      setState({ billing });
      if (billing.is_premium) renderManage(billing, providers);
      else renderOffer(billing, providers);
    } catch (error) {
      fill(body, errorState({ title: 'Не удалось загрузить тариф', onRetry: load }));
      logError('premium', error);
    }
  }

  // ---------------------------------------------------------------- offer (32)

  function renderOffer(billing, providers) {
    const stars = providers.find((p) => p.code === 'telegram_stars');
    const canPay = Boolean(stars && stars.enabled);

    const payButton = h('button.rm-btn', {
      style: { height: '56px', fontSize: '17px' },
      disabled: !canPay,
      onClick: () => startPayment(payButton),
    }, 'Получить Premium');

    fill(body, 
      h('div', { style: { paddingTop: '16px' } },
        h('div', {
          style: {
            width: '60px', height: '60px', borderRadius: '20px', background: 'var(--rm-surface-soft)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          },
        }, icons.star(28)),
        h('div', {
          style: {
            marginTop: '16px', fontSize: '32px', fontWeight: '800', color: 'var(--rm-green-dark)',
            letterSpacing: '-.02em', lineHeight: '1.1',
          },
        }, 'Remarka Premium'),
        h('div', {
          style: { marginTop: '8px', fontSize: '15px', lineHeight: '1.5', color: 'var(--rm-text-secondary)' },
        }, 'Больше AI по вашей библиотеке и новые возможности по мере развития приложения.'),

        h('div', { style: { marginTop: '20px', display: 'flex', flexDirection: 'column', gap: '10px' } },
          ...BENEFITS.map((benefit) =>
            h('div', {
              style: {
                display: 'flex', alignItems: 'center', gap: '12px', background: '#FFFFFF',
                borderRadius: '16px', boxShadow: '0 3px 12px rgba(20,60,35,.05)', padding: '14px 16px',
              },
            }, icons.check(19), h('div', { style: { fontSize: '15px' } }, benefit)),
          ),
        ),

        h('div', { style: { marginTop: '20px', display: 'flex', gap: '10px' } },
          planCard('Free', '0', `${freeLimit(billing)} AI-запросов в месяц`, 'Библиотека без ограничений', false),
          planCard('Premium', String(billing.premium_price_stars), 'В месяц', 'Больше AI и весь контекст', true),
        ),

        otherProviders(providers),
        h('div', { style: { height: '150px' } }),
      ),
      h('div', {
        style: {
          position: 'fixed', left: 0, right: 0, bottom: 0, background: '#FFFFFF',
          borderTop: '1px solid var(--rm-border-soft)',
          padding: '14px 20px calc(30px + var(--rm-safe-bottom))', textAlign: 'center', zIndex: '30',
        },
      },
        payButton,
        h('div', { style: { marginTop: '10px', fontSize: '13px', color: 'var(--rm-text-muted)' } },
          canPay
            ? 'Оплата через Telegram Stars · цена может измениться'
            : 'Оплата временно недоступна'),
      ),
    );
  }

  function freeLimit(billing) {
    return billing.is_premium ? 10 : billing.ai_limit;
  }

  function planCard(title, price, line1, line2, highlighted) {
    return h('div', {
      style: {
        flex: '1', borderRadius: '20px',
        border: highlighted ? '1.5px solid var(--rm-green)' : '1px solid var(--rm-border-strong)',
        background: highlighted ? 'var(--rm-surface-soft)' : '#FFFFFF', padding: '16px',
      },
    },
      h('div', {
        style: {
          fontSize: '15px', fontWeight: '700',
          color: highlighted ? 'var(--rm-green)' : 'var(--rm-text-muted)',
        },
      }, title),
      h('div', {
        style: {
          marginTop: '10px', fontSize: '22px', fontWeight: '800',
          color: highlighted ? 'var(--rm-green-dark)' : 'var(--rm-text)',
          display: 'flex', alignItems: 'center', gap: '5px',
        },
      }, price, icons.starSolid(19, highlighted ? '#027C41' : '#C2C7CD')),
      h('div', {
        style: {
          marginTop: '10px', fontSize: '13px', lineHeight: '1.5',
          color: highlighted ? '#4A6B55' : 'var(--rm-text-muted)',
        },
      }, line1, h('br'), line2),
    );
  }

  /** Disabled providers stay visible as "скоро", exactly as the backend reports them. */
  function otherProviders(providers) {
    const others = providers.filter((p) => p.code !== 'telegram_stars');
    if (!others.length) return null;
    return h('div', { style: { marginTop: '22px' } },
      h('div.rm-section-label', null, 'Другие способы оплаты'),
      h('div', {
        style: {
          marginTop: '10px', background: '#FFFFFF', borderRadius: '18px',
          boxShadow: 'var(--rm-shadow-card)', overflow: 'hidden',
        },
      },
        ...others.map((provider, index) =>
          h('div', {
            style: {
              minHeight: '52px', display: 'flex', alignItems: 'center', gap: '12px',
              padding: '0 16px', fontSize: '15px', color: 'var(--rm-text-muted)',
              borderBottom: index === others.length - 1 ? 'none' : '1px solid var(--rm-surface-grey)',
            },
          },
            h('div', { style: { flex: '1' } }, PROVIDER_LABELS[provider.code] || provider.code),
            h('div', {
              style: {
                height: '24px', padding: '0 10px', borderRadius: '12px',
                background: 'var(--rm-surface-grey)', fontSize: '12px', display: 'flex',
                alignItems: 'center', color: 'var(--rm-text-muted)',
              },
            }, provider.enabled ? 'Доступно' : 'Скоро'),
          ),
        ),
      ),
    );
  }

  // ---------------------------------------------------------------- payment

  async function startPayment(button) {
    haptic('light');
    button.disabled = true;
    fill(button, h('div.rm-spinner'));

    let invoice;
    try {
      invoice = await api.createStarsInvoice();
    } catch (error) {
      button.disabled = false;
      fill(button, document.createTextNode('Получить Premium'));
      toastError(error);
      return;
    }

    if (!invoice.invoice_url) {
      button.disabled = false;
      fill(button, document.createTextNode('Получить Premium'));
      showFailure('Не удалось создать счёт');
      return;
    }

    const status = await openInvoice(invoice.invoice_url);
    button.disabled = false;
    fill(button, document.createTextNode('Получить Premium'));

    if (status === 'unsupported') {
      showFailure('Оплата Telegram Stars доступна только внутри Telegram.');
      return;
    }
    if (status === 'cancelled') return;
    if (status === 'failed') {
      showFailure('Попробуйте ещё раз — списание не произошло.');
      return;
    }

    // 'paid' or 'pending': Telegram confirms via webhook, so wait for our backend.
    await waitForActivation(invoice.payment_id);
  }

  /** Polls our own backend — the subscription is only real once it says so. */
  async function waitForActivation(paymentId) {
    const sheet = openSheet({ dismissible: false },
      h('div', { style: { padding: '20px 0 8px', textAlign: 'center' } },
        h('div', {
          style: {
            width: '56px', height: '56px', margin: '0 auto', borderRadius: '50%',
            background: 'var(--rm-surface-soft)', display: 'flex', alignItems: 'center',
            justifyContent: 'center',
          },
        }, h('div.rm-spinner.rm-spinner--green', { style: { width: '26px', height: '26px' } })),
        h('div', { style: { marginTop: '18px', fontSize: '19px', fontWeight: '800', color: 'var(--rm-green-dark)' } },
          'Подтверждаем оплату'),
        h('div', { style: { marginTop: '8px', fontSize: '14px', color: 'var(--rm-text-secondary)' } },
          'Это занимает несколько секунд'),
      ),
    );

    for (let attempt = 0; attempt < 15; attempt += 1) {
      await sleep(attempt < 5 ? 1000 : 2000);
      try {
        const status = await api.getPaymentStatus(paymentId);
        if (status.is_premium || status.status === 'succeeded') {
          invalidate(keys.billing, keys.me, keys.aiUsage);
          sheet.close();
          showSuccess();
          return;
        }
        if (status.status === 'failed' || status.status === 'canceled') {
          sheet.close();
          showFailure('Попробуйте ещё раз — списание не произошло.');
          return;
        }
      } catch {
        /* keep polling: a transient error is not a payment failure */
      }
    }

    sheet.close();
    showPending();
  }

  /** Screen 33 — Premium activated. */
  async function showSuccess() {
    haptic('success');
    let billing = null;
    try {
      billing = await api.getBillingStatus();
      setState({ billing });
    } catch {
      /* the success screen does not depend on this */
    }

    const sheet = openSheet({ dismissible: false },
      h('div', { style: { padding: '12px 0 4px', textAlign: 'center' } },
        h('div', {
          style: {
            width: '72px', height: '72px', margin: '0 auto', borderRadius: '26px',
            background: 'var(--rm-surface-soft)', display: 'flex', alignItems: 'center',
            justifyContent: 'center',
          },
        }, icons.check(34, '#027C41', 2.8)),
        h('div', {
          style: { marginTop: '18px', fontSize: '24px', fontWeight: '800', color: 'var(--rm-green-dark)' },
        }, 'Premium активирован'),
        h('div', {
          style: { marginTop: '10px', fontSize: '15px', lineHeight: '1.5', color: 'var(--rm-text-secondary)' },
        }, 'Теперь вам доступны Premium-возможности Remarka'),
        billing && billing.expires_at
          ? h('div', {
              style: {
                marginTop: '18px', borderRadius: '20px', background: 'var(--rm-surface-soft)',
                padding: '16px', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              },
            },
              h('div', { style: { textAlign: 'left' } },
                h('div', { style: { fontSize: '15px', fontWeight: '700', color: 'var(--rm-green-dark)' } },
                  'Remarka Premium'),
                h('div', { style: { marginTop: '3px', fontSize: '13px', color: 'var(--rm-text-secondary)' } },
                  `Действует до ${formatShortDate(billing.expires_at)}`),
              ),
              h('div', {
                style: { display: 'flex', alignItems: 'center', gap: '5px', fontSize: '17px', fontWeight: '800' },
              }, String(billing.premium_price_stars), icons.starSolid(17)),
            )
          : null,
        h('button.rm-btn', {
          style: { marginTop: '22px' },
          onClick: () => { sheet.close(); load(); },
        }, 'Продолжить'),
      ),
    );
  }

  /** Screen 34 — payment failed. */
  function showFailure(text) {
    haptic('error');
    const sheet = openSheet({},
      h('div', { style: { padding: '12px 0 4px', textAlign: 'center' } },
        h('div', {
          style: {
            width: '72px', height: '72px', margin: '0 auto', borderRadius: '26px',
            background: 'var(--rm-danger-soft)', display: 'flex', alignItems: 'center',
            justifyContent: 'center',
          },
        }, icons.warning(32)),
        h('div', { style: { marginTop: '18px', fontSize: '21px', fontWeight: '800', color: 'var(--rm-green-dark)' } },
          'Не удалось провести оплату'),
        h('div', {
          style: { marginTop: '10px', fontSize: '15px', lineHeight: '1.5', color: 'var(--rm-text-secondary)' },
        }, text),
        h('div', { style: { marginTop: '22px', display: 'flex', flexDirection: 'column', gap: '10px' } },
          isTelegram()
            ? h('button.rm-btn', { onClick: () => { sheet.close(); load(); } }, 'Повторить')
            : null,
          h('button.rm-btn.rm-btn--quiet', { onClick: () => sheet.close() }, 'Закрыть'),
        ),
      ),
    );
  }

  function showPending() {
    const sheet = openSheet({},
      h('div', { style: { padding: '12px 0 4px', textAlign: 'center' } },
        h('div', { style: { fontSize: '20px', fontWeight: '800', color: 'var(--rm-green-dark)' } },
          'Оплата обрабатывается'),
        h('div', {
          style: { marginTop: '10px', fontSize: '15px', lineHeight: '1.5', color: 'var(--rm-text-secondary)' },
        }, 'Premium активируется автоматически, как только Telegram подтвердит платёж.'),
        h('button.rm-btn', { style: { marginTop: '22px' }, onClick: () => { sheet.close(); load(); } },
          'Обновить статус'),
      ),
    );
  }

  // ---------------------------------------------------------------- manage (35)

  function renderManage(billing, providers) {
    const active = providers.find((p) => p.code === 'telegram_stars');
    fill(body, 
      h('div', { style: { paddingTop: '16px', paddingBottom: '40px' } },
        h('div', {
          style: {
            borderRadius: '22px', background: 'var(--rm-surface-soft)', padding: '20px',
            display: 'flex', alignItems: 'center', gap: '16px',
          },
        },
          h('div', {
            style: {
              width: '52px', height: '52px', borderRadius: '18px', background: '#FFFFFF',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            },
          }, icons.star(24)),
          h('div', null,
            h('div', { style: { fontSize: '19px', fontWeight: '800', color: 'var(--rm-green-dark)' } },
              'Premium активен'),
            h('div', { style: { marginTop: '3px', fontSize: '14px', color: 'var(--rm-text-secondary)' } },
              'Спасибо, что поддерживаете Remarka'),
          ),
        ),

        h('div', {
          style: {
            marginTop: '16px', background: '#FFFFFF', borderRadius: '22px',
            boxShadow: 'var(--rm-shadow-card)', overflow: 'hidden',
          },
        },
          listRow({ label: 'Статус', value: 'Активен' }),
          listRow({ label: 'Следующий период', value: formatShortDate(billing.expires_at) || '—' }),
          listRow({ label: 'Стоимость', value: `${billing.premium_price_stars} ★ / месяц` }),
          listRow({
            label: 'Способ оплаты',
            value: active ? 'Telegram Stars' : '—',
            last: true,
          }),
        ),

        h('div', {
          style: {
            marginTop: '16px', background: '#FFFFFF', borderRadius: '22px',
            boxShadow: 'var(--rm-shadow-card)', padding: '18px',
          },
        },
          h('div', { style: { fontSize: '15px', fontWeight: '700' } }, 'AI-запросы'),
          h('div', { style: { marginTop: '6px', fontSize: '14px', color: 'var(--rm-text-secondary)' } },
            `${billing.ai_used} из ${billing.ai_limit} использовано в этом периоде`),
          h('div', {
            style: {
              marginTop: '12px', height: '8px', borderRadius: '4px', background: '#EDF2EE', overflow: 'hidden',
            },
          },
            h('div', {
              style: {
                width: `${Math.round((billing.ai_used / Math.max(billing.ai_limit, 1)) * 100)}%`,
                height: '100%', borderRadius: '4px', background: 'var(--rm-green)',
              },
            }),
          ),
        ),

        h('div', {
          style: {
            marginTop: '18px', fontSize: '13px', lineHeight: '1.5',
            color: 'var(--rm-text-muted)', textAlign: 'center',
          },
        }, 'Подписка управляется в Telegram: настройки → «Мои звёзды».'),

        h('button.rm-btn.rm-btn--ghost', {
          style: { marginTop: '18px' },
          onClick: () => navigate('/profile'),
        }, 'Вернуться в профиль'),
      ),
    );
  }
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
