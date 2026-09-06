/**
 * Screen 14 — "Новая книга".
 *
 * Two modes on one screen, matching the product flow: first search the catalog
 * (Google Books, topped up from Open Library), and fall back to the manual form
 * from the design when nothing matches.
 */

import { api } from '../api/client.js';
import { haptic } from '../api/telegram.js';
import { navigate } from '../router.js';
import { invalidate } from '../store.js';
import { icons } from '../ui/icons.js';
import { debounce, h, fill } from '../ui/dom.js';
import {
  backHeader,
  bookCover,
  chip,
  emptyState,
  footerBar,
  screen,
  skeletonBlock,
  toast,
  toastError,
  useTelegramBack,
  logError,
} from '../ui/components.js';
import { categoryPicker } from './category-picker.js';

export function addBookScreen() {
  const body = h('div');
  const view = screen({ header: backHeader('Новая книга') }, body);
  view.__cleanup = useTelegramBack('/');

  renderSearchMode();
  return view;

  // ---------------------------------------------------------------- search mode

  function renderSearchMode() {
    const results = h('div', { style: { marginTop: '18px' } });
    let value = '';

    const input = h('input', {
      type: 'search',
      placeholder: 'Название или автор',
      enterkeyhint: 'search',
      autocomplete: 'off',
      style: { flex: '1', fontSize: '16px' },
      onInput: (event) => { value = event.target.value; run(); },
    });

    const run = debounce(async () => {
      const q = value.trim();
      if (q.length < 2) {
        fill(results, searchHint());
        return;
      }
      fill(results, 
        h('div', { style: { display: 'flex', flexDirection: 'column', gap: '10px' } },
          skeletonBlock('86px', '18px'), skeletonBlock('86px', '18px'), skeletonBlock('86px', '18px')),
      );
      try {
        const found = await api.searchBooks(q, 20);
        renderResults(found, q);
      } catch (error) {
        fill(results, 
          emptyState({
            icon: icons.warning(28),
            title: 'Поиск недоступен',
            text: 'Можно добавить книгу вручную',
            actionLabel: 'Добавить вручную',
            onAction: () => renderManualMode({ title: value }),
          }),
        );
        logError('add-book', error);
      }
    }, 400);

    function searchHint() {
      return h('div', { style: { paddingTop: '30px', textAlign: 'center' } },
        h('div', { style: { fontSize: '15px', lineHeight: '1.5', color: 'var(--rm-text-muted)' } },
          'Найдите книгу в каталоге —', h('br'), 'обложка и автор подставятся сами'),
        h('button.rm-btn.rm-btn--ghost', {
          style: { marginTop: '20px', maxWidth: '260px', marginLeft: 'auto', marginRight: 'auto' },
          onClick: () => renderManualMode(),
        }, 'Добавить вручную'),
      );
    }

    function renderResults(found, q) {
      if (!found.length) {
        fill(results, 
          emptyState({
            icon: icons.search(30, '#8A9099'),
            title: 'Книга не найдена',
            text: `По запросу «${q}» ничего нет. Добавьте книгу вручную.`,
            actionLabel: 'Добавить вручную',
            onAction: () => renderManualMode({ title: q }),
          }),
        );
        return;
      }
      fill(results, 
        h('div', { style: { display: 'flex', flexDirection: 'column', gap: '10px' } },
          ...found.map(resultRow),
        ),
        h('button.rm-btn.rm-btn--ghost', {
          style: { marginTop: '18px' },
          onClick: () => renderManualMode({ title: q }),
        }, 'Нет нужной книги — добавить вручную'),
      );
    }

    function resultRow(item) {
      const button = h('button', {
        style: {
          width: '100%', background: '#FFFFFF', borderRadius: '18px', border: 'none',
          boxShadow: 'var(--rm-shadow-card)', padding: '12px', display: 'flex', gap: '12px',
          alignItems: 'center', textAlign: 'left',
        },
        onClick: () => addFromCatalog(item, button),
      },
        bookCover({ title: item.title, cover_url: item.cover_url },
          { width: '48px', height: '62px', radius: '10px', fontSize: 7 }),
        h('div', { style: { flex: '1', minWidth: 0 } },
          h('div', { style: { fontSize: '15px', fontWeight: '700', color: 'var(--rm-text)' } }, item.title),
          h('div', { style: { marginTop: '3px', fontSize: '13px', color: 'var(--rm-text-muted)' } },
            (item.authors || []).join(', ') || 'Автор не указан'),
          h('div', { style: { marginTop: '3px', fontSize: '12px', color: 'var(--rm-text-faint)' } },
            [item.published_year, item.publisher].filter(Boolean).join(' · ')),
        ),
        icons.plus(18, '#027C41', 2.4),
      );
      return button;
    }

    async function addFromCatalog(item, button) {
      haptic('light');
      button.disabled = true;
      button.style.opacity = '.6';
      try {
        const userBook = await api.addBook({
          source: item.source,
          source_id: item.source_id,
          title: item.title,
          subtitle: item.subtitle,
          authors: item.authors || [],
          description: item.description,
          isbn_10: item.isbn_10,
          isbn_13: item.isbn_13,
          published_year: item.published_year,
          publisher: item.publisher,
          cover_url: item.cover_url,
          category: (item.categories || [])[0] || null,
        });
        invalidate('library:');
        toast('Книга добавлена');
        navigate(`/book/${userBook.id}`, { replace: true });
      } catch (error) {
        button.disabled = false;
        button.style.opacity = '1';
        toastError(error);
      }
    }

    fill(body, 
      h('div', {
        style: {
          marginTop: '8px', height: '52px', borderRadius: '18px', background: '#FFFFFF',
          border: '1.5px solid var(--rm-green)', display: 'flex', alignItems: 'center',
          gap: '12px', padding: '0 16px',
        },
      }, icons.search(19), input),
      h('div', { style: { marginTop: '10px', fontSize: '13px', color: 'var(--rm-text-muted)' } },
        'Поиск по Google Books и Open Library'),
      results,
    );
    fill(results, searchHint());
    setTimeout(() => input.focus(), 80);
  }

  // ---------------------------------------------------------------- manual mode

  function renderManualMode(initial = {}) {
    const draft = {
      title: initial.title || '',
      author: '',
      category: null,
      description: '',
      cover_url: null,
    };

    const coverBox = h('div', {
      style: {
        width: '104px', height: '118px', flex: '0 0 auto', borderRadius: '16px',
        border: '1.5px dashed var(--rm-border-dashed)',
        backgroundImage: 'repeating-linear-gradient(135deg,#F4F8F5 0 9px,#FFFFFF 9px 18px)',
        display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
        gap: '8px', overflow: 'hidden',
      },
    },
      icons.upload(22),
      h('div', {
        style: { font: '500 10px/1.3 ui-monospace,Menlo,monospace', color: '#7E9B87', textAlign: 'center' },
      }, 'обложка', h('br'), 'JPG / PNG'),
    );

    const fileInput = h('input', {
      type: 'file',
      accept: 'image/jpeg,image/png,image/webp,image/gif',
      style: { display: 'none' },
      onChange: async (event) => {
        const file = event.target.files && event.target.files[0];
        if (!file) return;
        try {
          fill(coverBox, h('div.rm-spinner.rm-spinner--green'));
          const uploaded = await api.uploadCover(file);
          draft.cover_url = uploaded.url;
          coverBox.style.border = 'none';
          coverBox.style.backgroundImage = 'none';
          fill(coverBox, h('img', {
            src: uploaded.url,
            alt: '',
            style: { width: '100%', height: '100%', objectFit: 'cover' },
          }));
        } catch (error) {
          fill(coverBox, icons.upload(22));
          toastError(error);
        }
      },
    });

    const titleInput = h('input', {
      value: draft.title,
      placeholder: 'Например, Психология денег',
      style: { fontSize: '16px' },
      onInput: (event) => { draft.title = event.target.value; validate(); },
    });

    const authorInput = h('input', {
      placeholder: 'Например, Морган Хаузел',
      style: { fontSize: '16px' },
      onInput: (event) => { draft.author = event.target.value; },
    });

    const descriptionInput = h('textarea.rm-textarea', {
      placeholder: 'О чём эта книга для вас',
      style: { minHeight: '84px' },
      onInput: (event) => { draft.description = event.target.value; },
    });

    const categoryRow = h('div', { style: { display: 'flex', flexWrap: 'wrap', gap: '8px' } });
    const submit = h('button.rm-btn', { onClick: save, disabled: true }, 'Добавить книгу');

    function validate() {
      submit.disabled = draft.title.trim().length === 0;
    }

    async function paintCategories() {
      let categories = [];
      try {
        categories = await api.getCategories();
      } catch {
        categories = [];
      }
      fill(categoryRow, 
        ...categories.map((category) =>
          chip(category.name, {
            active: draft.category === category.name,
            onClick: () => {
              draft.category = draft.category === category.name ? null : category.name;
              paintCategories();
            },
          }),
        ),
        draft.category && !categories.some((c) => c.name === draft.category)
          ? chip(draft.category, { active: true, onClick: () => { draft.category = null; paintCategories(); } })
          : null,
        chip('+ Новая', {
          dashed: true,
          onClick: () =>
            categoryPicker({
              current: draft.category,
              onPick: (name) => { draft.category = name; paintCategories(); },
            }),
        }),
      );
    }

    async function save() {
      const title = draft.title.trim();
      if (!title) return;
      haptic('light');
      submit.disabled = true;
      fill(submit, h('div.rm-spinner'));
      try {
        const userBook = await api.addManualBook({
          title,
          authors: draft.author.trim() ? [draft.author.trim()] : [],
          description: draft.description.trim() || null,
          cover_url: draft.cover_url,
          category: draft.category,
        });
        invalidate('library:');
        toast('Книга добавлена');
        navigate(`/book/${userBook.id}`, { replace: true });
      } catch (error) {
        submit.disabled = false;
        fill(submit, document.createTextNode('Добавить книгу'));
        toastError(error);
      }
    }

    fill(body, 
      h('div', { style: { marginTop: '10px', display: 'flex', gap: '16px', alignItems: 'flex-start' } },
        coverBox,
        h('div', { style: { flex: '1', paddingTop: '6px' } },
          h('div', { style: { fontSize: '15px', fontWeight: '700' } }, 'Обложка'),
          h('div', {
            style: { marginTop: '6px', fontSize: '14px', lineHeight: '1.45', color: 'var(--rm-text-muted)' },
          }, 'Загрузите изображение или оставьте аккуратный placeholder'),
          h('button', {
            style: {
              marginTop: '12px', height: '42px', padding: '0 16px',
              border: '1px solid var(--rm-border-green)', borderRadius: '14px',
              background: 'var(--rm-surface-tint)', color: 'var(--rm-green-dark)',
              fontSize: '14px', fontWeight: '600',
            },
            onClick: () => fileInput.click(),
          }, 'Загрузить'),
          fileInput,
        ),
      ),
      h('div', { style: { marginTop: '20px', display: 'flex', flexDirection: 'column', gap: '14px' } },
        field('Название', titleInput, true),
        field('Автор', authorInput),
        h('div', null,
          h('div.rm-field-label', null, 'Категория'),
          categoryRow,
        ),
        h('div', null,
          h('div.rm-field-label', null,
            'Краткое описание ',
            h('span', { style: { color: 'var(--rm-text-placeholder)', fontWeight: '400' } },
              '— необязательно')),
          descriptionInput,
        ),
      ),
      h('div', { style: { height: '24px' } }),
      footerBar(
        h('button.rm-btn.rm-btn--ghost', { style: { flex: '1' }, onClick: () => renderSearchMode() }, 'Найти'),
        h('div', { style: { flex: '1.6', display: 'flex' } }, submit),
      ),
    );

    paintCategories();
    validate();
    setTimeout(() => titleInput.focus(), 80);
  }
}

export function field(label, control, required = false) {
  return h('div', null,
    h('div.rm-field-label', null, label, required ? h('span', { style: { color: 'var(--rm-green)' } }, ' *') : null),
    control.classList && control.classList.contains('rm-textarea')
      ? control
      : h('div.rm-input', null, control),
  );
}
