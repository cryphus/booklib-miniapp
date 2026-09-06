/** Screens 15–16 — editing a book in the library and removing it. */

import { api } from '../api/client.js';
import { haptic } from '../api/telegram.js';
import { navigate } from '../router.js';
import { invalidate, keys, query } from '../store.js';
import { h, fill } from '../ui/dom.js';
import {
  backHeader,
  bookCover,
  chip,
  confirmDialog,
  errorState,
  footerBar,
  screen,
  skeletonBlock,
  toast,
  toastError,
  useTelegramBack,
  logError,
} from '../ui/components.js';
import { categoryPicker } from './category-picker.js';

export function editBookScreen({ params }) {
  const userBookId = params.id;
  const body = h('div');
  const view = screen({ header: backHeader('Редактировать книгу') }, body);
  view.__cleanup = useTelegramBack(`/book/${userBookId}`);

  let userBook = null;
  let category = null;

  load();
  return view;

  async function load() {
    fill(body, skeletonBlock('150px', '22px', { marginTop: '18px' }));
    try {
      userBook = await query(keys.userBook(userBookId), () => api.getUserBook(userBookId),
        { ttl: 10_000, force: true });
      category = userBook.category ? userBook.category.name : null;
      render();
    } catch (error) {
      fill(body, errorState({ title: 'Не удалось открыть книгу', onRetry: load }));
      logError('edit-book', error);
    }
  }

  function render() {
    const book = userBook.book;
    const categoryRow = h('div', { style: { display: 'flex', flexWrap: 'wrap', gap: '8px' } });
    const saveButton = h('button.rm-btn', { onClick: save }, 'Сохранить изменения');

    async function paintCategories() {
      let categories = [];
      try {
        categories = await api.getCategories();
      } catch {
        categories = [];
      }
      const names = categories.map((c) => c.name);
      if (category && !names.includes(category)) names.unshift(category);

      fill(categoryRow, 
        ...names.map((name) =>
          chip(name, {
            active: category === name,
            onClick: () => { category = category === name ? null : name; paintCategories(); },
          }),
        ),
        chip('+ Новая', {
          dashed: true,
          onClick: () => categoryPicker({
            current: category,
            onPick: (name) => { category = name; paintCategories(); },
          }),
        }),
      );
    }

    async function save() {
      haptic('light');
      saveButton.disabled = true;
      fill(saveButton, h('div.rm-spinner'));
      try {
        await api.updateUserBook(userBookId, { category: category ?? '' });
        invalidate('library:', keys.userBook(userBookId), keys.categories);
        toast('Изменения сохранены');
        navigate(`/book/${userBookId}`, { replace: true });
      } catch (error) {
        saveButton.disabled = false;
        fill(saveButton, document.createTextNode('Сохранить изменения'));
        toastError(error);
      }
    }

    fill(body, 
      h('div', { style: { marginTop: '16px', display: 'flex', gap: '16px', alignItems: 'flex-start' } },
        bookCover(book, { width: '104px', height: '128px', radius: '16px', fontSize: 12 }),
        h('div', { style: { flex: '1', minWidth: 0, paddingTop: '4px' } },
          h('div', { style: { fontSize: '20px', fontWeight: '800', lineHeight: '1.2' } }, book.title),
          h('div', { style: { marginTop: '6px', fontSize: '14px', color: 'var(--rm-text-secondary)' } },
            (book.authors || []).join(', ') || 'Автор не указан'),
          book.published_year
            ? h('div', { style: { marginTop: '6px', fontSize: '13px', color: 'var(--rm-text-muted)' } },
                String(book.published_year))
            : null,
        ),
      ),

      h('div', {
        style: {
          marginTop: '16px', borderRadius: '16px', background: 'var(--rm-surface-tint)',
          border: '1px solid var(--rm-border-soft)', padding: '12px 14px', fontSize: '13px',
          lineHeight: '1.5', color: 'var(--rm-text-secondary)',
        },
      }, 'Название, автор и обложка берутся из общего каталога и одинаковы для всех читателей. Категория — только ваша.'),

      h('div', { style: { marginTop: '20px' } },
        h('div.rm-field-label', null, 'Категория'),
        categoryRow,
      ),

      h('button', {
        style: {
          marginTop: '28px', width: '100%', height: '52px', borderRadius: '18px',
          border: '1px solid #F3DADA', background: 'var(--rm-danger-soft)',
          color: 'var(--rm-danger)', fontSize: '16px', fontWeight: '600',
        },
        onClick: () =>
          confirmDialog({
            title: 'Удалить книгу?',
            text: 'Все цитаты и заметки этой книги будут удалены без возможности восстановления.',
            confirmLabel: 'Удалить книгу',
            onConfirm: async () => {
              try {
                await api.deleteUserBook(userBookId);
                invalidate('library:', 'entries:', 'search:', keys.userBook(userBookId));
                toast('Книга удалена');
                navigate('/', { replace: true });
              } catch (error) {
                toastError(error);
              }
            },
          }),
      }, 'Удалить книгу'),

      h('div', { style: { height: '120px' } }),
      footerBar(h('div', { style: { flex: '1', display: 'flex' } }, saveButton)),
    );

    paintCategories();
  }
}
