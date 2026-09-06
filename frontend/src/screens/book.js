/**
 * Screens 17–19 — a book in the library: header card, Все / Цитаты / Мои мысли / AI
 * filters, entry cards, the "…" menu and the "+" chooser.
 *
 * `?entry=<id>` opens the book scrolled to that entry and briefly highlights it,
 * which is how search results and AI sources link back here.
 */

import { api } from '../api/client.js';
import { haptic } from '../api/telegram.js';
import { navigate } from '../router.js';
import { invalidate, keys, query } from '../store.js';
import { icons, quoteGlyph } from '../ui/icons.js';
import { debounce, h, fill } from '../ui/dom.js';
import {
  backHeader,
  bookCover,
  confirmDialog,
  emptyState,
  errorState,
  formatShortDate,
  openActionSheet,
  plural,
  screen,
  skeletonBlock,
  toast,
  toastError,
  useTelegramBack,
  logError,
} from '../ui/components.js';

const TABS = [
  { key: 'all', label: 'Все', flex: '1' },
  { key: 'quote', label: 'Цитаты', flex: '1' },
  { key: 'note', label: 'Мои мысли', flex: '1.2' },
  { key: 'ai', label: 'AI', flex: '.7' },
];

export function bookScreen({ params, query: search }) {
  const userBookId = params.id;
  const focusEntryId = search.get('entry');

  let activeTab = 'all';
  let entryQuery = '';
  let userBook = null;

  const container = h('div');
  const entriesBox = h('div', {
    style: { marginTop: '14px', display: 'flex', flexDirection: 'column', gap: '12px' },
  });
  const tabsRow = h('div', { style: { marginTop: '12px', display: 'flex', gap: '8px' } });
  let allEntries = [];

  const filterEntries = debounce(() => {
    const needle = entryQuery.trim().toLowerCase();
    const visible = needle
      ? allEntries.filter((entry) =>
          `${entry.content} ${entry.personal_note || ''} ${entry.tags.map((t) => t.name).join(' ')}`
            .toLowerCase()
            .includes(needle))
      : allEntries;
    renderEntries(visible);
  }, 120);

  const view = screen({ tab: 'library', header: null }, container);
  view.__cleanup = useTelegramBack('/');

  load();
  return view;

  async function load() {
    fill(container, loadingSkeleton());
    try {
      userBook = await query(keys.userBook(userBookId), () => api.getUserBook(userBookId), {
        ttl: 15_000,
        force: true,
      });
      render();
      await loadEntries();
    } catch (error) {
      fill(container, 
        errorState({ title: 'Не удалось открыть книгу', onRetry: load }),
      );
      logError('book', error);
    }
  }

  function loadingSkeleton() {
    return h('div', { style: { paddingTop: '16px' } },
      skeletonBlock('158px', '22px'),
      skeletonBlock('50px', '18px', { marginTop: '14px' }),
      skeletonBlock('40px', '20px', { marginTop: '12px' }),
      skeletonBlock('120px', '20px', { marginTop: '14px' }),
      skeletonBlock('120px', '20px', { marginTop: '12px' }),
    );
  }

  // ---------------------------------------------------------------- layout

  function render() {
    const book = userBook.book;

    const favoriteButton = h('button.rm-icon-btn', {
      onClick: async () => {
        const next = !userBook.is_favorite;
        userBook.is_favorite = next;
        fill(favoriteButton, icons.bookmark(19, '#027C41', next));
        haptic('light');
        try {
          await api.setBookFavorite(userBook.id, next);
          invalidate('library:');
        } catch (error) {
          userBook.is_favorite = !next;
          fill(favoriteButton, icons.bookmark(19, '#027C41', !next));
          toastError(error);
        }
      },
      'aria-label': 'Избранное',
    }, icons.bookmark(19, '#027C41', userBook.is_favorite));

    const header = backHeader(null, null,
      h('div', { style: { display: 'flex', gap: '8px' } },
        favoriteButton,
        h('button.rm-icon-btn', {
          onClick: () => navigate(`/book/${userBook.id}/edit`),
          'aria-label': 'Редактировать книгу',
        }, icons.edit(19)),
      ),
    );

    const searchInput = h('input', {
      type: 'search',
      placeholder: 'Искать по сохранённому',
      style: { flex: '1', fontSize: '15px' },
      onInput: (event) => { entryQuery = event.target.value; filterEntries(); },
    });

    fill(container, 
      header,
      h('div', {
        style: {
          marginTop: '12px', borderRadius: '22px', background: 'var(--rm-surface-soft)',
          padding: '16px', display: 'flex', gap: '16px',
        },
      },
        bookCover(book, { width: '98px', height: '126px', radius: '14px', fontSize: 12 }),
        h('div', { style: { flex: '1', minWidth: 0 } },
          h('div', { style: { fontSize: '22px', fontWeight: '800', lineHeight: '1.15' } }, book.title),
          h('div', { style: { marginTop: '5px', fontSize: '15px', color: 'var(--rm-text-secondary)' } },
            (book.authors || []).join(', ') || 'Автор не указан'),
          userBook.category
            ? h('div', { style: { marginTop: '10px', fontSize: '14px', color: 'var(--rm-green)' } },
                userBook.category.name)
            : null,
          h('div', {
            style: {
              marginTop: '10px', display: 'flex', alignItems: 'center', gap: '7px',
              fontSize: '14px', color: 'var(--rm-text)',
            },
          }, icons.bookmark(16), plural(userBook.entries_count, 'сохранение', 'сохранения', 'сохранений')),
        ),
      ),
      h('div', {
        style: {
          marginTop: '14px', height: '50px', borderRadius: '18px', background: '#FFFFFF',
          border: '1px solid var(--rm-border)', display: 'flex', alignItems: 'center',
          gap: '12px', padding: '0 16px',
        },
      }, icons.search(19), searchInput),
      tabsRow,
      aiCard(),
      entriesBox,
      h('button.rm-fab', {
        onClick: openAddSheet,
        'aria-label': 'Добавить запись',
      }, icons.plus(28, '#FFFFFF', 2.4)),
    );

    renderTabs();
  }

  function renderTabs() {
    fill(tabsRow, 
      ...TABS.map((tab) =>
        h('button', {
          style: {
            flex: tab.flex, height: '40px', borderRadius: '20px',
            background: activeTab === tab.key ? 'var(--rm-green)' : '#FFFFFF',
            border: activeTab === tab.key ? 'none' : '1px solid var(--rm-border)',
            color: activeTab === tab.key ? '#FFFFFF' : 'var(--rm-text)',
            fontSize: '14px', fontWeight: activeTab === tab.key ? '600' : '400',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          },
          onClick: () => {
            haptic('selection');
            if (tab.key === 'ai') {
              // The AI tab opens the assistant scoped to this book.
              navigate(`/ai?context=current_book&book=${userBook.id}`);
              return;
            }
            activeTab = tab.key;
            renderTabs();
            loadEntries();
          },
        }, tab.label),
      ),
    );
  }

  function aiCard() {
    return h('button', {
      style: {
        marginTop: '12px', width: '100%', height: '64px', borderRadius: '18px',
        background: 'var(--rm-surface-soft)', border: 'none', display: 'flex',
        alignItems: 'center', gap: '12px', padding: '0 14px', textAlign: 'left',
      },
      onClick: () => navigate(`/ai?context=current_book&book=${userBook.id}`),
    },
      h('div', {
        style: {
          width: '40px', height: '40px', borderRadius: '14px', background: '#FFFFFF',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        },
      },
        h('div', {
          style: {
            width: '22px', height: '17px', borderRadius: '6px', background: 'var(--rm-green-bright)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '4px',
          },
        },
          h('div', { style: { width: '4px', height: '4px', borderRadius: '50%', background: '#FFFFFF' } }),
          h('div', { style: { width: '4px', height: '4px', borderRadius: '50%', background: '#FFFFFF' } }),
        ),
      ),
      h('div', { style: { flex: '1' } },
        h('div', { style: { fontSize: '15px', fontWeight: '700', color: 'var(--rm-green-dark)' } },
          'Спросить AI по этой книге'),
        h('div', { style: { marginTop: '2px', fontSize: '13px', color: 'var(--rm-text-secondary)' } },
          'Получите ответы и инсайты от AI'),
      ),
      icons.chevron(18, '#14532D'),
    );
  }

  // ---------------------------------------------------------------- entries

  async function loadEntries() {
    fill(entriesBox, skeletonBlock('120px', '20px'), skeletonBlock('120px', '20px'));
    const params = { page: 1, page_size: 50 };
    if (activeTab === 'quote' || activeTab === 'note') params.type = activeTab;

    try {
      const result = await query(keys.entries(userBookId, params),
        () => api.getBookEntries(userBookId, params), { ttl: 10_000, force: true });
      allEntries = result.items;
      filterEntries();
    } catch (error) {
      fill(entriesBox, errorState({ title: 'Не удалось загрузить записи', onRetry: loadEntries }));
      logError('book', error);
    }
  }

  function renderEntries(entries) {
    if (!entries.length) {
      fill(entriesBox, 
        entryQuery.trim()
          ? emptyState({ icon: icons.search(28, '#8A9099'), title: 'Ничего не найдено', text: 'Попробуйте другой запрос' })
          : emptyState({
              icon: activeTab === 'note' ? icons.note(28) : quoteGlyph(28),
              title: activeTab === 'note' ? 'Пока нет ваших мыслей' : 'Пока нет записей',
              text: 'Добавьте первую цитату или собственную мысль',
              actionLabel: 'Добавить запись',
              onAction: openAddSheet,
            }),
      );
      return;
    }
    fill(entriesBox, ...entries.map(entryCard));

    if (focusEntryId) {
      const target = entriesBox.querySelector(`[data-entry-id="${CSS.escape(focusEntryId)}"]`);
      if (target) {
        target.scrollIntoView({ behavior: 'smooth', block: 'center' });
        target.classList.add('rm-highlight');
        setTimeout(() => target.classList.remove('rm-highlight'), 2000);
      }
    }
  }

  function entryCard(entry) {
    const isQuote = entry.type === 'quote';
    const favoriteIcon = h('button', {
      style: { border: 'none', background: 'none', padding: '0', display: 'flex' },
      onClick: (event) => { event.stopPropagation(); toggleFavorite(entry, favoriteIcon); },
      'aria-label': 'Избранное',
    }, icons.bookmark(18, '#14532D', entry.is_favorite));

    const meta = h('div', {
      style: { marginTop: '12px', display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' },
    },
      isQuote && entry.chapter
        ? h('div', {
            style: { display: 'flex', alignItems: 'center', gap: '6px', fontSize: '13px', color: 'var(--rm-text-secondary)' },
          }, icons.chapter(15), `Глава ${entry.chapter}`)
        : h('div', { style: { fontSize: '13px', color: 'var(--rm-text-secondary)' } },
            [entry.chapter && `Глава ${entry.chapter}`, formatShortDate(entry.created_at)]
              .filter(Boolean).join(' · ')),
      h('div', { style: { marginLeft: 'auto', display: 'flex', gap: '6px', flexWrap: 'wrap' } },
        ...entry.tags.map((tag) =>
          h('div', {
            style: {
              height: '26px', padding: '0 11px', borderRadius: '13px',
              border: '1px solid var(--rm-border-green)', background: isQuote ? 'transparent' : '#FFFFFF',
              fontSize: '12px', color: 'var(--rm-green-dark)', display: 'flex', alignItems: 'center',
            },
          }, tag.name),
        ),
      ),
    );

    const card = h('div', {
      dataset: { entryId: entry.id },
      style: isQuote
        ? {
            background: '#FFFFFF', borderRadius: '20px', boxShadow: 'var(--rm-shadow-card-strong)',
            padding: '14px',
          }
        : {
            background: 'var(--rm-surface-tint)', border: '1px solid #EAF0EC',
            borderRadius: '20px', padding: '14px',
          },
      onClick: () => openEntryMenu(entry),
    },
      h('div', { style: { display: 'flex', gap: '10px', alignItems: 'flex-start' } },
        isQuote
          ? quoteGlyph(30)
          : h('div', {
              style: {
                width: '30px', height: '30px', flex: '0 0 auto', borderRadius: '10px',
                background: '#FFFFFF', border: '1px solid var(--rm-border-green)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              },
            }, icons.note(16)),
        h('div', { style: { flex: '1', minWidth: 0 } },
          isQuote
            ? null
            : h('div', {
                style: {
                  fontSize: '12px', fontWeight: '700', letterSpacing: '.04em',
                  textTransform: 'uppercase', color: 'var(--rm-green)',
                },
              }, 'Моя мысль'),
          h('div', {
            style: {
              marginTop: isQuote ? '0' : '5px', fontSize: '15px', lineHeight: '1.45',
              fontWeight: isQuote ? '600' : '400', color: 'var(--rm-text)',
            },
          }, entry.content),
        ),
        h('div', { style: { display: 'flex', gap: '10px', paddingTop: '2px' } },
          favoriteIcon,
          h('button', {
            style: { border: 'none', background: 'none', padding: '0', display: 'flex' },
            onClick: (event) => { event.stopPropagation(); openEntryMenu(entry); },
            'aria-label': 'Действия',
          }, icons.dots(18)),
        ),
      ),
      meta,
      isQuote && entry.personal_note
        ? h('div', {
            style: { marginTop: '12px', paddingTop: '12px', borderTop: '1px solid var(--rm-border-soft)' },
          },
            h('div', { style: { fontSize: '13px', fontWeight: '700', color: 'var(--rm-green)' } }, 'Моя заметка:'),
            h('div', {
              style: { marginTop: '4px', fontSize: '13px', lineHeight: '1.5', color: '#4A5158' },
            }, entry.personal_note),
          )
        : null,
    );
    return card;
  }

  async function toggleFavorite(entry, iconButton) {
    const next = !entry.is_favorite;
    entry.is_favorite = next;
    fill(iconButton, icons.bookmark(18, '#14532D', next));
    haptic('light');
    try {
      await api.setEntryFavorite(entry.id, next);
      invalidate('entries:', 'search:');
    } catch (error) {
      entry.is_favorite = !next;
      fill(iconButton, icons.bookmark(18, '#14532D', !next));
      toastError(error);
    }
  }

  // ---------------------------------------------------------------- sheets

  /** Screen 18 — the "…" menu on an entry. */
  function openEntryMenu(entry) {
    haptic('light');
    openActionSheet({
      title: entry.type === 'quote' ? 'Цитата' : 'Моя мысль',
      subtitle: [entry.chapter && `Глава ${entry.chapter}`, userBook.book.title].filter(Boolean).join(' · '),
      actions: [
        {
          label: 'Редактировать',
          icon: icons.edit(18),
          onSelect: () => navigate(`/entry/${entry.id}/edit`),
        },
        {
          label: entry.is_favorite ? 'Убрать из избранного' : 'В избранное',
          icon: icons.bookmark(18, '#14532D', entry.is_favorite),
          onSelect: async () => {
            try {
              await api.setEntryFavorite(entry.id, !entry.is_favorite);
              invalidate('entries:', 'search:');
              loadEntries();
            } catch (error) {
              toastError(error);
            }
          },
        },
        {
          label: 'Удалить',
          icon: icons.trash(18),
          danger: true,
          onSelect: () =>
            confirmDialog({
              title: 'Удалить запись?',
              text: 'Запись будет удалена без возможности восстановления.',
              confirmLabel: 'Удалить запись',
              onConfirm: async () => {
                try {
                  await api.deleteEntry(entry.id);
                  invalidate('entries:', 'library:', 'search:', keys.userBook(userBookId));
                  toast('Запись удалена');
                  await load();
                } catch (error) {
                  toastError(error);
                }
              },
            }),
        },
      ],
    });
  }

  /** Screen 19 — what would you like to add? */
  function openAddSheet() {
    haptic('light');
    openActionSheet({
      title: 'Что хотите добавить?',
      subtitle: `${userBook.book.title} · ${(userBook.book.authors || []).join(', ')}`,
      actions: [
        {
          label: 'Цитату',
          description: 'Текст из книги, глава и страница',
          icon: quoteGlyph(30),
          onSelect: () => navigate(`/book/${userBook.id}/entry/new?type=quote`),
        },
        {
          label: 'Мою мысль',
          description: 'Собственный вывод или идея',
          icon: h('div', {
            style: {
              width: '30px', height: '30px', borderRadius: '10px', background: '#FFFFFF',
              border: '1px solid var(--rm-border-green)', display: 'flex',
              alignItems: 'center', justifyContent: 'center',
            },
          }, icons.note(16)),
          onSelect: () => navigate(`/book/${userBook.id}/entry/new?type=note`),
        },
      ],
    });
  }
}
