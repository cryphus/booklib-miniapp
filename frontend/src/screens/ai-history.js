/** Screens 27 & 30 — AI conversation history, with delete and the empty state. */

import { api } from '../api/client.js';
import { navigate } from '../router.js';
import { invalidate, keys, query } from '../store.js';
import { icons } from '../ui/icons.js';
import { h, fill } from '../ui/dom.js';
import {
  backHeader,
  confirmDialog,
  emptyState,
  errorState,
  formatDate,
  plural,
  screen,
  skeletonBlock,
  toast,
  toastError,
  useTelegramBack,
  logError,
} from '../ui/components.js';

export function aiHistoryScreen() {
  const list = h('div', { style: { marginTop: '18px', display: 'flex', flexDirection: 'column', gap: '10px' } });
  const view = screen({ tab: 'ai', header: backHeader('История', null, null, { onBack: () => navigate('/ai') }) }, list);
  view.__cleanup = useTelegramBack('/ai');

  load();
  return view;

  async function load() {
    fill(list, skeletonBlock('76px', '18px'), skeletonBlock('76px', '18px'), skeletonBlock('76px', '18px'));
    try {
      const result = await query(keys.conversations, () => api.getConversations({ page_size: 50 }),
        { ttl: 10_000, force: true });
      render(result.items);
    } catch (error) {
      fill(list, errorState({ title: 'Не удалось загрузить историю', onRetry: load }));
      logError('ai-history', error);
    }
  }

  function render(items) {
    if (!items.length) {
      fill(list, 
        emptyState({
          icon: icons.history(30),
          title: 'История пока пуста',
          text: 'Задайте первый вопрос Remarka AI — диалог сохранится здесь',
          actionLabel: 'Спросить AI',
          onAction: () => navigate('/ai'),
        }),
      );
      return;
    }
    fill(list, ...items.map(row));
  }

  function row(conversation) {
    const contextLabel = {
      all_library: 'Все книги',
      current_book: 'Текущая книга',
      favorites: 'Избранное',
    }[conversation.context_type] || 'Все книги';

    const answers = Math.max(Math.floor(conversation.messages_count / 2), 0);

    return h('div', {
      style: {
        background: '#FFFFFF', borderRadius: '18px', boxShadow: 'var(--rm-shadow-card)',
        padding: '14px', display: 'flex', alignItems: 'center', gap: '12px',
      },
    },
      h('button', {
        style: { flex: '1', minWidth: 0, border: 'none', background: 'none', textAlign: 'left', padding: '0' },
        onClick: () => navigate(`/ai/${conversation.id}`),
      },
        h('div', {
          style: {
            fontSize: '16px', fontWeight: '700', overflow: 'hidden',
            textOverflow: 'ellipsis', whiteSpace: 'nowrap',
          },
        }, conversation.title),
        h('div', { style: { marginTop: '4px', fontSize: '13px', color: 'var(--rm-text-muted)' } },
          [formatDate(conversation.updated_at), contextLabel,
            answers ? plural(answers, 'ответ', 'ответа', 'ответов') : null]
            .filter(Boolean).join(' · ')),
      ),
      h('button', {
        style: {
          width: '38px', height: '38px', flex: '0 0 auto', borderRadius: '14px',
          background: 'var(--rm-danger-soft)', border: 'none', display: 'flex',
          alignItems: 'center', justifyContent: 'center',
        },
        onClick: () =>
          confirmDialog({
            title: 'Удалить диалог?',
            text: 'История этого диалога будет удалена без возможности восстановления.',
            confirmLabel: 'Удалить диалог',
            onConfirm: async () => {
              try {
                await api.deleteConversation(conversation.id);
                invalidate(keys.conversations);
                toast('Диалог удалён');
                load();
              } catch (error) {
                toastError(error);
              }
            },
          }),
        'aria-label': 'Удалить диалог',
      }, icons.trash(17)),
    );
  }
}
