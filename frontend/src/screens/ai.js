/**
 * Screens 24–26, 28–29 — Remarka AI.
 *
 * Start state with suggestions, the dialog with real source cards, the
 * "nothing found" state and the quota-exceeded sheet. Every source card links
 * back to the exact entry it came from.
 */

import { ApiError, api } from '../api/client.js';
import { haptic } from '../api/telegram.js';
import { navigate } from '../router.js';
import { getState, invalidate, keys, query, setState } from '../store.js';
import { aiAvatar, aiMark, icons } from '../ui/icons.js';
import { h, fill } from '../ui/dom.js';
import {
  backHeader,
  bookCover,
  emptyState,
  errorState,
  openSheet,
  pageHeader,
  plural,
  screen,
  toastError,
  useTelegramBack,
  logError,
} from '../ui/components.js';

const CONTEXTS = [
  { key: 'all_library', label: 'Все книги' },
  { key: 'current_book', label: 'Текущая книга' },
  { key: 'favorites', label: 'Избранное' },
];

const SUGGESTIONS = [
  'Найди мысли про управление капиталом',
  'Собери цитаты про дисциплину',
  'Сравни идеи из двух книг',
];

export function aiScreen({ params, query: search }) {
  const state = {
    conversationId: params.conversationId || null,
    contextType: search.get('context') || 'all_library',
    contextBookId: search.get('book') || null,
    contextBookTitle: null,
    messages: [],
    sending: false,
    usage: getState().me ? getState().me.ai_usage : null,
  };

  const thread = h('div', { style: { paddingTop: '4px' } });
  const container = h('div');
  const view = screen({ tab: 'ai', header: null, footer: null }, container);
  view.__cleanup = useTelegramBack('/');

  const composerInput = h('input', {
    placeholder: 'Спросить по вашим заметкам…',
    enterkeyhint: 'send',
    maxlength: '1000',
    style: { flex: '1', fontSize: '15px' },
    onKeydown: (event) => { if (event.key === 'Enter') send(); },
  });

  const sendButton = h('button', {
    style: {
      width: '48px', height: '48px', flex: '0 0 auto', borderRadius: '50%',
      background: 'var(--rm-green)', border: 'none', display: 'flex',
      alignItems: 'center', justifyContent: 'center', boxShadow: '0 6px 16px rgba(2,124,65,.28)',
    },
    onClick: send,
    'aria-label': 'Отправить',
  }, icons.send());

  const composer = h('div', {
    style: {
      position: 'fixed', left: 0, right: 0,
      bottom: 'calc(var(--rm-tabbar-height) + var(--rm-safe-bottom))',
      padding: '10px 20px', background: '#FFFFFF', borderTop: '1px solid var(--rm-border-soft)',
      display: 'flex', alignItems: 'center', gap: '10px', zIndex: '25',
    },
  },
    h('button', {
      style: {
        width: '44px', height: '44px', flex: '0 0 auto', borderRadius: '50%',
        background: 'var(--rm-surface-grey)', border: 'none', display: 'flex',
        alignItems: 'center', justifyContent: 'center',
      },
      onClick: startNewConversation,
      'aria-label': 'Новый диалог',
    }, icons.plus(20, '#14532D', 2.2)),
    h('div', {
      style: {
        flex: '1', height: '48px', borderRadius: '24px', background: '#FFFFFF',
        border: '1px solid var(--rm-border)', display: 'flex', alignItems: 'center', padding: '0 18px',
      },
    }, composerInput),
    sendButton,
  );

  init();
  return view;

  // ---------------------------------------------------------------- init

  async function init() {
    if (state.contextBookId) {
      try {
        const userBook = await query(keys.userBook(state.contextBookId),
          () => api.getUserBook(state.contextBookId), { ttl: 60_000 });
        state.contextBookTitle = userBook.book.title;
      } catch {
        state.contextType = 'all_library';
        state.contextBookId = null;
      }
    }

    if (state.conversationId) {
      try {
        const conversation = await api.getConversation(state.conversationId);
        state.messages = conversation.messages;
        state.contextType = conversation.context_type;
        state.contextBookId = conversation.context_user_book_id;
      } catch (error) {
        fill(container, errorState({ title: 'Диалог не найден', onRetry: () => navigate('/ai') }));
        logError('ai', error);
        return;
      }
    }

    await refreshUsage();
    render();

    const preset = search.get('q');
    if (preset) {
      composerInput.value = preset;
      send();
    }
  }

  async function refreshUsage() {
    try {
      state.usage = await query(keys.aiUsage, () => api.getAiUsage(), { ttl: 10_000, force: true });
    } catch {
      /* the ask call reports the real quota anyway */
    }
  }

  // ---------------------------------------------------------------- render

  function render() {
    fill(container, 
      state.messages.length ? dialogHeader() : startHeader(),
      thread,
      composer,
    );
    renderThread();
  }

  function startHeader() {
    return h('div', null,
      pageHeader('AI помощник', 'Спроси по своим заметкам и книгам',
        h('button.rm-icon-btn', {
          onClick: () => navigate('/ai/history'),
          'aria-label': 'История диалогов',
        }, icons.history()),
      ),
      contextChips(),
    );
  }

  function dialogHeader() {
    const title = state.messages.find((m) => m.role === 'user');
    return backHeader(
      title ? truncate(title.content, 28) : 'Новый вопрос',
      contextLabel(),
      h('button.rm-icon-btn', {
        style: { width: '40px', height: '40px' },
        onClick: () => navigate('/ai/history'),
        'aria-label': 'История',
      }, icons.history()),
      { onBack: () => (state.messages.length ? startNewConversation() : navigate('/')) },
    );
  }

  function contextLabel() {
    if (state.contextType === 'current_book') return `Текущая книга · ${state.contextBookTitle || ''}`;
    if (state.contextType === 'favorites') return 'Избранное';
    return 'Все книги';
  }

  function contextChips() {
    const row = h('div.rm-chips-row', { style: { marginTop: '16px' } });
    fill(row, 
      ...CONTEXTS.map((context) => {
        const disabled = context.key === 'current_book' && !state.contextBookId;
        return h('button', {
          class: `rm-chip${state.contextType === context.key ? ' rm-chip--active' : ''}`,
          style: { height: '40px', borderRadius: '20px', color: disabled ? 'var(--rm-text-faint)' : undefined },
          onClick: () => {
            if (disabled) {
              openContextSheet();
              return;
            }
            state.contextType = context.key;
            haptic('selection');
            render();
          },
        }, context.label);
      }),
      h('button.rm-chip', {
        style: { width: '44px', height: '40px', borderRadius: '20px', padding: '0', justifyContent: 'center' },
        onClick: openContextSheet,
        'aria-label': 'Где искать',
      }, icons.filters(18)),
    );
    return row;
  }

  function renderThread() {
    if (!state.messages.length) {
      fill(thread, startCard(), usageNote());
      return;
    }
    fill(thread, 
      ...state.messages.map((message) =>
        message.role === 'user' ? userBubble(message) : assistantBlock(message)),
      h('div', { style: { height: '90px' } }),
    );
    thread.lastElementChild.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }

  /** Screen 24 — the greeting card with example questions. */
  function startCard() {
    return h('div', {
      style: {
        marginTop: '14px', background: '#FFFFFF', borderRadius: '22px',
        boxShadow: 'var(--rm-shadow-card-strong)', padding: '16px',
      },
    },
      h('div', { style: { display: 'flex', gap: '12px' } },
        aiAvatar(44),
        h('div', null,
          h('div', { style: { fontSize: '17px', fontWeight: '700' } }, 'Привет! Я Remarka AI'),
          h('div', {
            style: { marginTop: '4px', fontSize: '14px', lineHeight: '1.45', color: 'var(--rm-text-secondary)' },
          }, 'Помогу найти ответы в твоих книгах и заметках. Вот что можно спросить:'),
        ),
      ),
      h('div', { style: { marginTop: '14px', display: 'flex', flexDirection: 'column', gap: '10px' } },
        ...SUGGESTIONS.map((suggestion) =>
          h('button', {
            style: {
              minHeight: '54px', borderRadius: '16px', background: 'var(--rm-surface-tint)',
              border: '1px solid #EFF3F0', display: 'flex', alignItems: 'center', gap: '12px',
              padding: '10px 14px', textAlign: 'left',
            },
            onClick: () => { composerInput.value = suggestion; send(); },
          },
            icons.sparkle(18),
            h('div', { style: { flex: '1', fontSize: '15px' } }, suggestion),
            icons.chevron(16),
          ),
        ),
      ),
    );
  }

  function usageNote() {
    if (!state.usage) return null;
    const { used, limit, remaining, plan } = state.usage;
    return h('div', {
      style: {
        marginTop: '18px', display: 'flex', alignItems: 'center', gap: '10px',
        padding: '0 4px', fontSize: '13px', color: 'var(--rm-text-muted)',
      },
    },
      h('div', { style: { flex: '1', height: '1px', background: 'var(--rm-divider)' } }),
      h('div', null,
        plan === 'premium'
          ? `Premium · осталось ${remaining} из ${limit}`
          : `Осталось ${remaining} из ${limit} AI-запросов`),
      h('div', { style: { flex: '1', height: '1px', background: 'var(--rm-divider)' } }),
    );
  }

  function userBubble(message) {
    return h('div', {
      style: { display: 'flex', justifyContent: 'flex-end', gap: '10px', alignItems: 'flex-end', marginTop: '16px' },
    },
      h('div', {
        style: {
          maxWidth: '260px', background: 'var(--rm-surface-mint)',
          borderRadius: '20px 20px 6px 20px', padding: '12px 14px',
        },
      },
        h('div', { style: { fontSize: '15px', lineHeight: '1.45' } }, message.content),
        h('div', {
          style: { marginTop: '6px', textAlign: 'right', fontSize: '11px', color: '#6E9179' },
        }, new Date(message.created_at).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })),
      ),
      h('div', {
        style: {
          width: '34px', height: '34px', flex: '0 0 auto', borderRadius: '50%',
          background: 'var(--rm-surface-grey)', display: 'flex', alignItems: 'center',
          justifyContent: 'center',
        },
      }, icons.user(17, '#027C41')),
    );
  }

  function assistantBlock(message) {
    const hasSources = message.sources && message.sources.length > 0;
    return h('div', { style: { marginTop: '16px', display: 'flex', gap: '10px' } },
      aiAvatar(34),
      h('div', { style: { flex: '1', minWidth: 0 } },
        h('div', {
          style: {
            background: '#FFFFFF', borderRadius: '20px', boxShadow: 'var(--rm-shadow-card-strong)',
            padding: '14px', fontSize: '15px', lineHeight: '1.5', whiteSpace: 'pre-wrap',
          },
        }, message.content),
        hasSources
          ? h('div', null,
              h('div', { style: { marginTop: '12px', display: 'flex', alignItems: 'center', gap: '8px' } },
                h('div', {
                  style: {
                    fontSize: '12px', fontWeight: '700', letterSpacing: '.06em',
                    textTransform: 'uppercase', color: 'var(--rm-text-muted)',
                  },
                }, `Источники · ${message.sources.length}`),
                h('div', { style: { flex: '1', height: '1px', background: 'var(--rm-divider)' } }),
              ),
              h('div', { style: { marginTop: '10px', display: 'flex', flexDirection: 'column', gap: '10px' } },
                ...message.sources.map(sourceCard),
              ),
            )
          : noContextActions(),
      ),
    );
  }

  /** Screen 25 — a real source card that navigates to the entry it cites. */
  function sourceCard(source) {
    const isNote = source.entry_type === 'note';
    return h('button', {
      style: {
        width: '100%', textAlign: 'left', border: isNote ? '1px solid #EAF0EC' : 'none',
        background: isNote ? 'var(--rm-surface-tint)' : '#FFFFFF', borderRadius: '18px',
        boxShadow: isNote ? 'none' : 'var(--rm-shadow-card)', padding: '10px',
        display: 'flex', gap: '10px', alignItems: 'center',
      },
      onClick: () => {
        haptic('light');
        navigate(`/book/${source.user_book_id}?entry=${source.entry_id}`);
      },
    },
      isNote
        ? h('div', {
            style: {
              width: '52px', height: '66px', flex: '0 0 auto', borderRadius: '10px',
              background: '#FFFFFF', border: '1px solid #E4EEE7', display: 'flex',
              alignItems: 'center', justifyContent: 'center',
            },
          }, icons.note(22))
        : bookCover({ title: source.book_title, cover_url: source.book_cover_url },
            { width: '52px', height: '66px', radius: '10px', fontSize: 7 }),
      h('div', { style: { flex: '1', minWidth: 0 } },
        h('div', {
          style: {
            fontSize: '14px', fontWeight: '700', overflow: 'hidden',
            textOverflow: 'ellipsis', whiteSpace: 'nowrap',
          },
        }, isNote ? 'Моя мысль' : source.book_title),
        h('div', {
          style: {
            marginTop: '3px', display: 'flex', alignItems: 'center', gap: '6px',
            fontSize: '11px', color: 'var(--rm-green)',
          },
        },
          h('span', {
            style: { width: '5px', height: '5px', borderRadius: '50%', background: 'var(--rm-green)' },
          }),
          [isNote ? 'Мысль' : 'Цитата', source.chapter && `Глава ${source.chapter}`,
            source.page && `с. ${source.page}`].filter(Boolean).join(' · '),
        ),
        h('div', {
          style: { marginTop: '4px', fontSize: '12px', lineHeight: '1.4', color: 'var(--rm-text-secondary)' },
        }, source.snippet),
      ),
      icons.chevron(16),
    );
  }

  /** Screen 26 — the assistant found nothing, so it offers real next steps. */
  function noContextActions() {
    const action = (label, onClick) =>
      h('button', {
        style: {
          width: '100%', minHeight: '48px', borderRadius: '16px', background: 'var(--rm-surface-tint)',
          border: '1px solid #EFF3F0', display: 'flex', alignItems: 'center', gap: '10px',
          padding: '10px 14px', fontSize: '14px', textAlign: 'left',
        },
        onClick,
      }, icons.sparkle(16), h('div', { style: { flex: '1' } }, label), icons.chevron(15));

    return h('div', { style: { marginTop: '12px', display: 'flex', flexDirection: 'column', gap: '8px' } },
      action('Сформулировать вопрос иначе', () => composerInput.focus()),
      state.contextType !== 'all_library'
        ? action('Искать по всей библиотеке', () => {
            state.contextType = 'all_library';
            state.contextBookId = null;
            startNewConversation();
          })
        : null,
      action('Добавить цитату или мысль', () => navigate('/')),
    );
  }

  // ---------------------------------------------------------------- actions

  function startNewConversation() {
    state.conversationId = null;
    state.messages = [];
    composerInput.value = '';
    navigate(state.contextBookId
      ? `/ai?context=${state.contextType}&book=${state.contextBookId}`
      : '/ai');
    render();
  }

  async function send() {
    const question = composerInput.value.trim();
    if (!question || state.sending) return;

    if (state.usage && state.usage.remaining <= 0) {
      openLimitSheet();
      return;
    }

    state.sending = true;
    fill(sendButton, h('div.rm-spinner'));
    composerInput.value = '';
    haptic('light');

    state.messages.push({
      id: `local-${Date.now()}`,
      role: 'user',
      content: question,
      sources: [],
      created_at: new Date().toISOString(),
    });
    if (state.messages.length === 1) render();
    else renderThread();
    appendThinking();

    try {
      const response = state.conversationId
        ? await api.askInConversation(state.conversationId, question)
        : await api.ask(question, state.contextType, state.contextBookId);

      state.conversationId = response.conversation_id;
      state.usage = response.usage;
      setState({ aiUsage: response.usage });
      state.messages.push(response.message);
      invalidate(keys.conversations, keys.aiUsage);
      renderThread();
    } catch (error) {
      state.messages.pop();
      if (error instanceof ApiError && error.isAiLimitReached) {
        await refreshUsage();
        renderThread();
        openLimitSheet();
      } else {
        renderThread();
        toastError(error);
        composerInput.value = question; // don't lose what the user typed
      }
    } finally {
      state.sending = false;
      fill(sendButton, icons.send());
    }
  }

  function appendThinking() {
    const node = h('div', { style: { marginTop: '16px', display: 'flex', gap: '10px' } },
      aiAvatar(34),
      h('div', {
        style: {
          background: '#FFFFFF', borderRadius: '20px', boxShadow: 'var(--rm-shadow-card-strong)',
          padding: '16px 18px',
        },
      }, h('div.rm-typing', null, h('span'), h('span'), h('span'))),
    );
    thread.appendChild(node);
    node.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }

  /** Screen 28 — "Где искать". */
  async function openContextSheet() {
    haptic('light');
    let stats = null;
    try {
      stats = await query(keys.stats, () => api.getStats(), { ttl: 60_000 });
    } catch {
      stats = null;
    }

    const option = (key, title, subtitle, iconNode, disabled = false) => {
      const active = state.contextType === key;
      return h('button', {
        style: {
          width: '100%', minHeight: '66px', borderRadius: '20px',
          background: active ? 'var(--rm-surface-soft)' : '#FFFFFF',
          border: active ? '1.5px solid var(--rm-green)' : '1px solid var(--rm-border-strong)',
          display: 'flex', alignItems: 'center', gap: '14px', padding: '0 16px',
          textAlign: 'left', opacity: disabled ? '.6' : '1',
        },
        onClick: () => {
          if (disabled) return;
          state.contextType = key;
          sheet.close();
          startNewConversation();
        },
      },
        h('div', {
          style: {
            width: '40px', height: '40px', borderRadius: '14px',
            background: active ? '#FFFFFF' : 'var(--rm-surface-grey)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          },
        }, iconNode),
        h('div', { style: { flex: '1' } },
          h('div', {
            style: {
              fontSize: '16px', fontWeight: '700',
              color: active ? 'var(--rm-green-dark)' : 'var(--rm-text)',
            },
          }, title),
          h('div', {
            style: { fontSize: '13px', color: disabled ? 'var(--rm-text-placeholder)' : 'var(--rm-text-secondary)' },
          }, subtitle),
        ),
        active ? icons.check(18) : null,
      );
    };

    const sheet = openSheet({ title: 'Где искать', subtitle: 'AI будет использовать только выбранный контекст' },
      h('div', { style: { marginTop: '18px', display: 'flex', flexDirection: 'column', gap: '10px' } },
        option('all_library', 'Во всей библиотеке',
          stats ? `${plural(stats.books_count, 'книга', 'книги', 'книг')} · ${plural(stats.entries_count, 'запись', 'записи', 'записей')}` : 'Все ваши записи',
          icons.library(20)),
        option('current_book', 'В текущей книге',
          state.contextBookTitle || 'Книга не открыта',
          icons.book(20), !state.contextBookId),
        option('favorites', 'В избранном',
          stats ? plural(stats.favorites_count, 'запись', 'записи', 'записей') : 'Только избранное',
          icons.bookmark(20, '#027C41', true)),
        h('button.rm-btn', { style: { marginTop: '8px' }, onClick: () => sheet.close() }, 'Готово'),
      ),
    );
  }

  /** Screen 29 — free AI requests exhausted. */
  function openLimitSheet() {
    const price = getState().billing ? getState().billing.premium_price_stars : null;
    const sheet = openSheet({},
      h('div', { style: { paddingTop: '4px' } },
        h('div', {
          style: {
            width: '64px', height: '64px', borderRadius: '22px', background: 'var(--rm-surface-soft)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          },
        }, aiMark(30, 23)),
        h('div', {
          style: {
            marginTop: '18px', fontSize: '22px', fontWeight: '800',
            color: 'var(--rm-green-dark)', lineHeight: '1.2',
          },
        }, 'Бесплатные AI-запросы закончились'),
        h('div', {
          style: { marginTop: '10px', fontSize: '15px', lineHeight: '1.5', color: 'var(--rm-text-secondary)' },
        }, 'Вы использовали все AI-запросы текущего периода.'),
        h('div', {
          style: { marginTop: '18px', borderRadius: '22px', background: 'var(--rm-surface-soft)', padding: '18px' },
        },
          h('div', { style: { display: 'flex', alignItems: 'center', justifyContent: 'space-between' } },
            h('div', { style: { fontSize: '17px', fontWeight: '800', color: 'var(--rm-green-dark)' } },
              'Remarka Premium'),
            price
              ? h('div', {
                  style: {
                    height: '28px', padding: '0 12px', borderRadius: '14px', background: '#FFFFFF',
                    fontSize: '13px', fontWeight: '600', color: 'var(--rm-green)',
                    display: 'flex', alignItems: 'center', gap: '4px',
                  },
                }, String(price), icons.starSolid(14), '/ мес')
              : null,
          ),
          h('div', { style: { marginTop: '14px', display: 'flex', flexDirection: 'column', gap: '10px' } },
            ...['Больше AI-запросов каждый месяц', 'AI по всей библиотеке сразу',
              'Расширенные возможности Remarka AI'].map((text) =>
              h('div', {
                style: { display: 'flex', alignItems: 'center', gap: '10px', fontSize: '14px' },
              }, icons.check(17), text),
            ),
          ),
        ),
        h('div', { style: { marginTop: '18px', display: 'flex', flexDirection: 'column', gap: '10px' } },
          h('button.rm-btn', {
            style: { height: '56px', fontSize: '17px' },
            onClick: () => { sheet.close(); navigate('/premium'); },
          }, 'Получить Premium'),
          h('button.rm-btn.rm-btn--quiet', { onClick: () => sheet.close() }, 'Позже'),
        ),
      ),
    );
  }
}

function truncate(text, length) {
  const value = String(text || '').trim();
  return value.length > length ? `${value.slice(0, length - 1)}…` : value;
}

export { emptyState };
