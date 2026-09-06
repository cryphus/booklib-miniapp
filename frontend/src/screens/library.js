/**
 * Screens 06–10, 13 — "Моя библиотека": grid, filters sheet, and the loading /
 * empty / empty-category / error states.
 */

import { api } from '../api/client.js';
import { haptic } from '../api/telegram.js';
import { navigate } from '../router.js';
import { invalidate, keys, query } from '../store.js';
import { icons } from '../ui/icons.js';
import { h, fill } from '../ui/dom.js';
import {
  bookCover,
  chip,
  emptyState,
  errorState,
  librarySkeleton,
  openSheet,
  pageHeader,
  screen,
  switchControl,
  toastError,
} from '../ui/components.js';

const PAGE_SIZE = 20;

const filters = { category: null, favorite: false, sort: 'recent' };

export function libraryScreen() {
  const grid = h('div', { style: { marginTop: '16px' } });
  const chipsRow = h('div.rm-chips-row', { style: { marginTop: '14px' } });
  let page = 1;
  let loading = false;
  let exhausted = false;
  let items = [];

  const header = pageHeader('Моя библиотека', 'Сохраняй важное из прочитанного',
    [
      h('button.rm-icon-btn', { onClick: openFilters, 'aria-label': 'Фильтры' }, icons.filters()),
      h('button.rm-icon-btn.rm-icon-btn--green', {
        onClick: () => { haptic('light'); navigate('/books/add'); },
        'aria-label': 'Добавить книгу',
      }, icons.plus()),
    ],
  );

  const searchBar = h('button', {
    style: {
      marginTop: '16px', width: '100%', height: '52px', borderRadius: '18px', background: '#FFFFFF',
      border: '1px solid var(--rm-border)', boxShadow: '0 2px 8px rgba(20,60,35,.04)',
      display: 'flex', alignItems: 'center', gap: '12px', padding: '0 18px',
    },
    onClick: () => navigate('/search'),
  }, icons.search(), h('div', { style: { fontSize: '16px', color: 'var(--rm-text-placeholder)' } },
    'Найти книгу или заметку'));

  const view = screen({ tab: 'library' }, header, searchBar, chipsRow, grid);

  // ---------------------------------------------------------------- data

  async function loadCategories() {
    try {
      const categories = await query(keys.categories, () => api.getCategories(), { ttl: 120_000 });
      renderChips(categories);
    } catch {
      renderChips([]); // categories are decoration; the grid still works without them
    }
  }

  async function load({ reset = false } = {}) {
    if (loading) return;
    loading = true;
    if (reset) {
      page = 1;
      exhausted = false;
      items = [];
      fill(grid, librarySkeleton());
    }

    const params = {
      page,
      page_size: PAGE_SIZE,
      sort: filters.sort,
      category: filters.category || undefined,
      favorite: filters.favorite ? true : undefined,
    };

    try {
      const result = await query(keys.library(params), () => api.getLibrary(params), {
        ttl: 15_000,
        force: reset,
      });
      items = page === 1 ? result.items : items.concat(result.items);
      exhausted = !result.has_more;
      renderGrid();
    } catch (error) {
      fill(grid, errorState({
        title: 'Не удалось загрузить библиотеку',
        onRetry: () => load({ reset: true }),
      }));
      if (page > 1) toastError(error);
    } finally {
      loading = false;
    }
  }

  // ---------------------------------------------------------------- render

  function renderChips(categories) {
    fill(chipsRow, 
      chip('Все', {
        active: !filters.category,
        onClick: () => { filters.category = null; load({ reset: true }); renderChips(categories); },
      }),
      ...categories.map((category) =>
        chip(category.name, {
          active: filters.category === category.name,
          onClick: () => {
            filters.category = category.name;
            load({ reset: true });
            renderChips(categories);
          },
        }),
      ),
    );
    chipsRow.style.display = categories.length ? 'flex' : 'none';
  }

  function renderGrid() {
    if (!items.length) {
      fill(grid, 
        filters.category
          ? emptyState({
              icon: icons.library(30),
              title: 'Здесь пока нет книг',
              text: `В категории «${filters.category}» ничего не сохранено`,
              actionLabel: 'Показать все книги',
              onAction: () => { filters.category = null; loadCategories(); load({ reset: true }); },
            })
          : filters.favorite
            ? emptyState({
                icon: icons.bookmark(30, '#027C41'),
                title: 'В избранном пусто',
                text: 'Отметьте книгу закладкой, чтобы она появилась здесь',
                actionLabel: 'Сбросить фильтр',
                onAction: () => { filters.favorite = false; load({ reset: true }); },
              })
            : emptyState({
                icon: icons.library(30),
                title: 'В библиотеке пока пусто',
                text: 'Добавьте первую книгу, чтобы сохранять цитаты и заметки',
                actionLabel: 'Добавить книгу',
                onAction: () => navigate('/books/add'),
              }),
      );
      return;
    }

    fill(grid, 
      h('div', { style: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px' } },
        ...items.map(bookCard),
      ),
      exhausted
        ? null
        : h('button', {
            style: {
              marginTop: '18px', width: '100%', height: '46px', borderRadius: '16px',
              background: 'var(--rm-surface-tint)', border: '1px solid var(--rm-border-soft)',
              color: 'var(--rm-green-dark)', fontSize: '15px', fontWeight: '600',
            },
            onClick: (event) => {
              event.currentTarget.textContent = 'Загрузка…';
              page += 1;
              load();
            },
          }, 'Показать ещё'),
    );
  }

  /** Two per row, exactly as in the design — the grid above owns the columns. */
  function bookCard(userBook) {
    const cover = bookCover(userBook.book, { aspect: '1 / 1.18', radius: '14px' });

    const favoriteButton = h('button', {
      style: {
        position: 'absolute', top: '8px', right: '8px', width: '30px', height: '30px',
        borderRadius: '50%', background: 'rgba(255,255,255,.86)', border: 'none',
        display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '0',
      },
      onClick: async (event) => {
        event.stopPropagation();
        const next = !userBook.is_favorite;
        userBook.is_favorite = next; // optimistic: a bookmark toggle is safe to show at once
        fill(favoriteButton, icons.bookmark(15, '#027C41', next));
        haptic('light');
        try {
          await api.setBookFavorite(userBook.id, next);
          invalidate('library:');
        } catch (error) {
          userBook.is_favorite = !next;
          fill(favoriteButton, icons.bookmark(15, '#027C41', !next));
          toastError(error);
        }
      },
      'aria-label': userBook.is_favorite ? 'Убрать из избранного' : 'В избранное',
    }, icons.bookmark(15, '#027C41', userBook.is_favorite));

    cover.appendChild(favoriteButton);

    return h('div', {
      style: {
        background: '#FFFFFF', borderRadius: '20px', boxShadow: 'var(--rm-shadow-card)',
        padding: '10px', cursor: 'pointer',
      },
      onClick: () => { haptic('light'); navigate(`/book/${userBook.id}`); },
    },
      cover,
      h('div', {
        style: {
          padding: '10px 4px 4px', fontSize: '15px', fontWeight: '700',
          color: 'var(--rm-text)', lineHeight: '1.25',
        },
      }, userBook.book.title),
      h('div', { style: { padding: '0 4px', fontSize: '13px', color: 'var(--rm-green)' } },
        userBook.category ? userBook.category.name : (userBook.book.authors || []).join(', ')),
    );
  }

  // ---------------------------------------------------------------- filters sheet

  function openFilters() {
    haptic('light');
    const draft = { ...filters };
    const container = h('div');
    const sheet = openSheet({ title: 'Фильтры' }, container);

    api.getCategories().then(renderSheet).catch(() => renderSheet([]));

    function renderSheet(list) {
      const categoryChips = h('div', {
        style: { marginTop: '10px', display: 'flex', flexWrap: 'wrap', gap: '8px' },
      });

      const paint = () => {
        fill(categoryChips, 
          chip('Все', { active: !draft.category, onClick: () => { draft.category = null; paint(); } }),
          ...list.map((category) =>
            chip(category.name, {
              active: draft.category === category.name,
              onClick: () => { draft.category = category.name; paint(); },
            }),
          ),
        );
      };
      paint();

      const favoriteRow = h('div', {
        style: {
          marginTop: '22px', height: '56px', borderRadius: '18px', background: 'var(--rm-surface-tint)',
          border: '1px solid var(--rm-border-soft)', display: 'flex', alignItems: 'center',
          justifyContent: 'space-between', padding: '0 16px',
        },
      },
        h('div', { style: { display: 'flex', alignItems: 'center', gap: '10px' } },
          icons.bookmark(20, '#027C41', true),
          h('div', { style: { fontSize: '16px' } }, 'Только избранное'),
        ),
        switchControl(draft.favorite, (value) => { draft.favorite = value; renderSheet(list); }),
      );

      const sortOption = (value, label, last = false) =>
        h('button', {
          style: {
            width: '100%', height: '52px', display: 'flex', alignItems: 'center',
            justifyContent: 'space-between', padding: '0 16px', border: 'none',
            borderBottom: last ? 'none' : '1px solid var(--rm-border-soft)',
            background: draft.sort === value ? 'var(--rm-surface-tint)' : '#FFFFFF',
            fontSize: '16px', fontWeight: draft.sort === value ? '600' : '400', textAlign: 'left',
          },
          onClick: () => { draft.sort = value; renderSheet(list); },
        },
          h('div', null, label),
          draft.sort === value ? icons.check(18) : null,
        );

      fill(container, 
        h('div.rm-section-label', { style: { marginTop: '20px' } }, 'Категория'),
        categoryChips,
        favoriteRow,
        h('div.rm-section-label', { style: { marginTop: '22px' } }, 'Сортировка'),
        h('div', {
          style: {
            marginTop: '10px', borderRadius: '18px', border: '1px solid var(--rm-border)',
            overflow: 'hidden',
          },
        },
          sortOption('recent', 'Сначала новые'),
          sortOption('oldest', 'Сначала старые'),
          sortOption('title', 'По названию', true),
        ),
        h('div', { style: { marginTop: '22px', display: 'flex', gap: '10px' } },
          h('button.rm-btn.rm-btn--ghost', {
            style: { flex: '1' },
            onClick: () => {
              draft.category = null;
              draft.favorite = false;
              draft.sort = 'recent';
              renderSheet(list);
            },
          }, 'Сбросить'),
          h('button.rm-btn', {
            style: { flex: '1.4' },
            onClick: () => {
              Object.assign(filters, draft);
              sheet.close();
              loadCategories();
              load({ reset: true });
            },
          }, 'Применить'),
        ),
      );
    }
  }

  loadCategories();
  load({ reset: true });
  return view;
}
