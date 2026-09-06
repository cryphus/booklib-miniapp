/**
 * Screens 11–12 — global search over the user's own books, quotes, notes and tags.
 * Tapping a result opens the book and scrolls to the exact entry.
 */

import { api } from '../api/client.js';
import { haptic } from '../api/telegram.js';
import { back, navigate } from '../router.js';
import { keys, query } from '../store.js';
import { icons, quoteGlyph } from '../ui/icons.js';
import { debounce, h, highlight, fill } from '../ui/dom.js';
import {
  bookCover,
  emptyState,
  errorState,
  screen,
  skeletonBlock,
  useTelegramBack,
  logError,
} from '../ui/components.js';

export function searchScreen({ query: params }) {
  const results = h('div', { style: { marginTop: '18px' } });
  let value = params.get('q') || '';

  const input = h('input', {
    type: 'search',
    value,
    placeholder: 'Найти книгу или заметку',
    autocomplete: 'off',
    enterkeyhint: 'search',
    style: { flex: '1', fontSize: '16px', color: 'var(--rm-text)' },
    onInput: (event) => { value = event.target.value; run(); },
  });

  const clearButton = h('button', {
    style: {
      width: '20px', height: '20px', borderRadius: '50%', background: 'var(--rm-border)',
      border: 'none', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '0',
    },
    onClick: () => { input.value = ''; value = ''; input.focus(); run(); },
    'aria-label': 'Очистить',
  }, icons.close(9));

  const bar = h('div', {
    style: { padding: 'calc(var(--rm-safe-top) + 10px) 20px 0', display: 'flex', alignItems: 'center', gap: '10px' },
  },
    h('div', {
      style: {
        flex: '1', height: '52px', borderRadius: '18px', background: '#FFFFFF',
        border: '1.5px solid var(--rm-green)', display: 'flex', alignItems: 'center',
        gap: '10px', padding: '0 16px',
      },
    }, icons.search(19), input, clearButton),
    h('button', {
      style: { border: 'none', background: 'none', fontSize: '16px', color: 'var(--rm-green)', fontWeight: '500' },
      onClick: () => back('/'),
    }, 'Отмена'),
  );

  const view = screen({ tab: 'library', header: bar }, results);
  const detachBack = useTelegramBack('/');
  view.__cleanup = detachBack;

  const run = debounce(async () => {
    const q = value.trim();
    if (!q) {
      fill(results, hint());
      return;
    }
    fill(results, loadingList());
    try {
      const data = await query(keys.search(q), () => api.search(q, 20), { ttl: 10_000 });
      render(data, q);
    } catch (error) {
      fill(results, errorState({ title: 'Поиск не удался', onRetry: run }));
      logError('search', error);
    }
  }, 280);

  function hint() {
    return h('div', { style: { paddingTop: '40px', textAlign: 'center', color: 'var(--rm-text-muted)' } },
      h('div', { style: { fontSize: '15px', lineHeight: '1.5' } },
        'Ищите по названиям книг, авторам,', h('br'), 'цитатам, мыслям и тегам'),
    );
  }

  function loadingList() {
    return h('div', { style: { display: 'flex', flexDirection: 'column', gap: '10px' } },
      skeletonBlock('72px', '18px'), skeletonBlock('72px', '18px'), skeletonBlock('96px', '18px'));
  }

  function render(data, q) {
    if (!data.total) {
      fill(results, 
        emptyState({
          icon: icons.search(30, '#8A9099'),
          title: 'Ничего не найдено',
          text: 'Попробуйте другой запрос или спросите Remarka AI',
          actionLabel: 'Спросить AI',
          onAction: () => navigate(`/ai?q=${encodeURIComponent(q)}`),
        }),
      );
      return;
    }

    fill(results, 
      section('Книги', data.books.length, data.books.map((item) => bookRow(item, q))),
      section('Цитаты', data.quotes.length, data.quotes.map((item) => entryRow(item, q))),
      section('Мои мысли', data.notes.length, data.notes.map((item) => entryRow(item, q))),
    );
  }

  function section(title, count, nodes) {
    if (!count) return null;
    return h('div', { style: { marginBottom: '20px' } },
      h('div.rm-section-label', { style: { marginBottom: '10px' } }, `${title} · ${count}`),
      h('div', { style: { display: 'flex', flexDirection: 'column', gap: '10px' } }, nodes),
    );
  }

  function bookRow(userBook, q) {
    return h('div', {
      style: {
        background: '#FFFFFF', borderRadius: '18px', boxShadow: 'var(--rm-shadow-card)',
        padding: '12px', display: 'flex', gap: '12px', alignItems: 'center', cursor: 'pointer',
      },
      onClick: () => { haptic('light'); navigate(`/book/${userBook.id}`); },
    },
      bookCover(userBook.book, { width: '44px', height: '58px', radius: '10px', fontSize: 7 }),
      h('div', { style: { flex: '1', minWidth: 0 } },
        h('div', { style: { fontSize: '15px', fontWeight: '700', color: 'var(--rm-text)' } },
          highlight(userBook.book.title, q)),
        h('div', { style: { marginTop: '3px', fontSize: '13px', color: 'var(--rm-text-muted)' } },
          (userBook.book.authors || []).join(', ')),
        userBook.category
          ? h('div', { style: { marginTop: '3px', fontSize: '13px', color: 'var(--rm-green)' } },
              userBook.category.name)
          : null,
      ),
      icons.chevron(),
    );
  }

  function entryRow(entry, q) {
    const meta = [entry.book && entry.book.title, entry.chapter && `Глава ${entry.chapter}`]
      .filter(Boolean)
      .join(' · ');

    return h('div', {
      style: {
        background: '#FFFFFF', borderRadius: '18px', boxShadow: 'var(--rm-shadow-card)',
        padding: '14px', cursor: 'pointer',
      },
      // Opens the book and highlights this entry, per the design's navigation note.
      onClick: () => { haptic('light'); navigate(`/book/${entry.user_book_id}?entry=${entry.id}`); },
    },
      h('div', { style: { display: 'flex', gap: '10px' } },
        entry.type === 'quote' ? quoteGlyph(26) : icons.note(22),
        h('div', { style: { fontSize: '14px', lineHeight: '1.45', color: 'var(--rm-text)' } },
          highlight(entry.content, q)),
      ),
      h('div', {
        style: {
          marginTop: '10px', display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap',
        },
      },
        meta ? h('div', { style: { fontSize: '12px', color: 'var(--rm-text-muted)' } }, meta) : null,
        ...entry.tags.slice(0, 2).map((tag) =>
          h('div', {
            style: {
              height: '24px', padding: '0 10px', borderRadius: '12px',
              border: '1px solid var(--rm-border-green)', fontSize: '12px',
              color: 'var(--rm-green-dark)', display: 'flex', alignItems: 'center',
            },
          }, tag.name),
        ),
      ),
    );
  }

  if (value) run();
  else fill(results, hint());
  setTimeout(() => input.focus(), 60);

  return view;
}
