/**
 * Screens 20–23 — creating and editing a quote or a personal note, including the
 * tag picker sheet. One screen covers both, because the design differs only in
 * labels and the presence of the "Моя заметка" field.
 */

import { api } from '../api/client.js';
import { haptic } from '../api/telegram.js';
import { back, navigate } from '../router.js';
import { invalidate, keys, query } from '../store.js';
import { icons } from '../ui/icons.js';
import { h, fill } from '../ui/dom.js';
import {
  backHeader,
  confirmDialog,
  footerBar,
  openSheet,
  screen,
  tagPill,
  toast,
  toastError,
  useTelegramBack,
} from '../ui/components.js';

const MAX_CONTENT = 10000;
const MAX_NOTE = 5000;
const MAX_TAGS = 15;

export function entryFormScreen({ params, query: search }) {
  const editing = Boolean(params.entryId);
  const type = search.get('type') === 'note' ? 'note' : 'quote';

  const state = {
    type,
    content: '',
    personal_note: '',
    chapter: '',
    page: '',
    tags: [],
    userBookId: params.id || null,
    bookTitle: '',
    entryId: params.entryId || null,
  };

  const body = h('div');
  const view = screen({ header: null }, body);
  view.__cleanup = useTelegramBack('/');

  init();
  return view;

  async function init() {
    try {
      if (editing) {
        const entry = await api.getEntry(state.entryId);
        state.type = entry.type;
        state.content = entry.content;
        state.personal_note = entry.personal_note || '';
        state.chapter = entry.chapter || '';
        state.page = entry.page || '';
        state.tags = entry.tags.map((tag) => tag.name);
        state.userBookId = entry.user_book_id;
        state.bookTitle = entry.book ? entry.book.title : '';
      } else {
        const userBook = await query(keys.userBook(state.userBookId),
          () => api.getUserBook(state.userBookId), { ttl: 60_000 });
        state.bookTitle = userBook.book.title;
      }
      render();
    } catch (error) {
      toastError(error);
      back('/');
    }
  }

  function render() {
    const isQuote = state.type === 'quote';
    const title = editing
      ? (isQuote ? 'Редактировать цитату' : 'Редактировать мысль')
      : (isQuote ? 'Новая цитата' : 'Моя мысль');

    const contentInput = h('textarea.rm-textarea', {
      placeholder: isQuote
        ? 'Текст цитаты из книги'
        : 'Ваш собственный вывод или идея',
      maxlength: String(MAX_CONTENT),
      style: { border: '1.5px solid var(--rm-green)' },
      onInput: (event) => {
        state.content = event.target.value;
        counter.textContent = `${state.content.length} / ${MAX_CONTENT}`;
        validate();
      },
    });
    contentInput.value = state.content;

    const counter = h('div', {
      style: { marginTop: '6px', textAlign: 'right', fontSize: '12px', color: 'var(--rm-text-faint)' },
    }, `${state.content.length} / ${MAX_CONTENT}`);

    const chapterInput = h('input', {
      value: state.chapter,
      placeholder: 'Глава 2',
      maxlength: '128',
      style: { fontSize: '16px' },
      onInput: (event) => { state.chapter = event.target.value; },
    });

    const pageInput = h('input', {
      value: state.page,
      placeholder: '—',
      maxlength: '32',
      style: { fontSize: '16px' },
      onInput: (event) => { state.page = event.target.value; },
    });

    const noteInput = h('textarea.rm-textarea', {
      placeholder: 'Что вы об этом думаете',
      maxlength: String(MAX_NOTE),
      style: { minHeight: '90px' },
      onInput: (event) => { state.personal_note = event.target.value; },
    });
    noteInput.value = state.personal_note;

    const tagsRow = h('div', { style: { display: 'flex', flexWrap: 'wrap', gap: '8px' } });
    const saveButton = h('button.rm-btn', { onClick: save }, editing ? 'Сохранить изменения' : 'Сохранить');

    function validate() {
      saveButton.disabled = state.content.trim().length === 0;
    }

    function renderTags() {
      fill(tagsRow, 
        ...state.tags.map((name) =>
          tagPill(name, {
            filled: true,
            onRemove: () => {
              state.tags = state.tags.filter((tag) => tag !== name);
              renderTags();
            },
          }),
        ),
        state.tags.length < MAX_TAGS
          ? h('button.rm-chip.rm-chip--dashed', {
              style: { height: '34px', borderRadius: '17px', fontSize: '13px' },
              onClick: openTagSheet,
            }, '+ Добавить')
          : null,
      );
    }

    function openTagSheet() {
      haptic('light');
      const selected = new Set(state.tags);
      let filter = '';
      const listBox = h('div', {
        style: { marginTop: '16px', display: 'flex', flexWrap: 'wrap', gap: '8px' },
      });
      const createBox = h('div', { style: { marginTop: '14px' } });

      const input = h('input', {
        placeholder: 'Поиск или новая тема',
        maxlength: '64',
        style: { fontSize: '16px' },
        onInput: (event) => { filter = event.target.value; paint(); },
        onKeydown: (event) => { if (event.key === 'Enter') createFromInput(); },
      });

      const sheet = openSheet({ title: 'Темы', subtitle: `Выбрано ${selected.size}` },
        h('div', { style: { marginTop: '16px' } },
          h('div.rm-input', null, input),
          listBox,
          createBox,
          h('button.rm-btn', {
            style: { marginTop: '20px' },
            onClick: () => {
              state.tags = [...selected].slice(0, MAX_TAGS);
              sheet.close();
              renderTags();
            },
          }, 'Готово'),
        ),
      );

      let available = [];

      function createFromInput() {
        const name = filter.trim();
        if (!name || selected.has(name)) return;
        selected.add(name);
        filter = '';
        input.value = '';
        paint();
      }

      function paint() {
        const needle = filter.trim().toLowerCase();
        const options = available.filter((tag) => !needle || tag.name.toLowerCase().includes(needle));
        const merged = [...new Set([...selected, ...options.map((tag) => tag.name)])];

        fill(listBox, 
          ...merged.map((name) => {
            const active = selected.has(name);
            return h('button', {
              class: `rm-chip${active ? ' rm-chip--active' : ''}`,
              style: { height: '34px', borderRadius: '17px', fontSize: '13px' },
              onClick: () => {
                if (active) selected.delete(name);
                else if (selected.size < MAX_TAGS) selected.add(name);
                else toast(`Не больше ${MAX_TAGS} тегов на запись`, { type: 'error' });
                paint();
              },
            }, name);
          }),
        );

        const typed = filter.trim();
        fill(createBox, 
          typed && !merged.some((name) => name.toLowerCase() === typed.toLowerCase())
            ? h('button.rm-btn.rm-btn--ghost', {
                style: { height: '46px', fontSize: '15px' },
                onClick: createFromInput,
              }, `Создать тег «${typed}»`)
            : null,
        );

        const subtitle = sheet.element.querySelector('.rm-sheet__title')?.nextElementSibling;
        if (subtitle) subtitle.textContent = `Выбрано ${selected.size}`;
      }

      api.getTags().then((tags) => { available = tags; paint(); }).catch(() => paint());
      paint();
      setTimeout(() => input.focus(), 120);
    }

    async function save() {
      const content = state.content.trim();
      if (!content) return;
      haptic('light');
      saveButton.disabled = true;
      fill(saveButton, h('div.rm-spinner'));

      const payload = {
        content,
        chapter: state.chapter.trim() || null,
        page: state.page.trim() || null,
        tags: state.tags,
      };
      if (state.type === 'quote') payload.personal_note = state.personal_note.trim() || null;

      try {
        if (editing) {
          await api.updateEntry(state.entryId, payload);
          toast('Изменения сохранены');
        } else {
          await api.createEntry(state.userBookId, { ...payload, type: state.type });
          toast(state.type === 'quote' ? 'Цитата сохранена' : 'Мысль сохранена');
        }
        invalidate('entries:', 'library:', 'search:', 'ai:', keys.userBook(state.userBookId), keys.tags);
        navigate(`/book/${state.userBookId}`, { replace: true });
      } catch (error) {
        saveButton.disabled = false;
        fill(saveButton, document.createTextNode(editing ? 'Сохранить изменения' : 'Сохранить'));
        toastError(error);
      }
    }

    fill(body, 
      backHeader(title, state.bookTitle,
        h('button', {
          style: { border: 'none', background: 'none', fontSize: '16px', fontWeight: '600', color: 'var(--rm-green)' },
          onClick: save,
        }, 'Сохранить'),
      ),
      h('div', { style: { marginTop: '14px' } },
        h('div.rm-field-label', null,
          isQuote ? 'Текст цитаты' : 'Моя мысль',
          h('span', { style: { color: 'var(--rm-green)' } }, ' *')),
        contentInput,
        counter,
      ),
      h('div', { style: { marginTop: '10px', display: 'flex', gap: '12px' } },
        h('div', { style: { flex: '1.4' } },
          h('div.rm-field-label', null, 'Глава'),
          h('div.rm-input', { style: { height: '52px' } }, chapterInput),
        ),
        h('div', { style: { flex: '1' } },
          h('div.rm-field-label', null, 'Страница'),
          h('div.rm-input', { style: { height: '52px' } }, pageInput),
        ),
      ),
      isQuote
        ? h('div', { style: { marginTop: '16px' } },
            h('div.rm-field-label', null, 'Моя заметка ',
              h('span', { style: { color: 'var(--rm-text-placeholder)', fontWeight: '400' } },
                '— необязательно')),
            noteInput,
          )
        : null,
      h('div', { style: { marginTop: '16px' } },
        h('div.rm-field-label', null, 'Теги / темы'),
        tagsRow,
      ),
      editing
        ? h('button', {
            style: {
              marginTop: '26px', width: '100%', height: '50px', borderRadius: '16px',
              border: '1px solid #F3DADA', background: 'var(--rm-danger-soft)',
              color: 'var(--rm-danger)', fontSize: '15px', fontWeight: '600',
            },
            onClick: () =>
              confirmDialog({
                title: 'Удалить запись?',
                text: 'Запись будет удалена без возможности восстановления.',
                confirmLabel: 'Удалить запись',
                onConfirm: async () => {
                  try {
                    await api.deleteEntry(state.entryId);
                    invalidate('entries:', 'library:', 'search:', keys.userBook(state.userBookId));
                    toast('Запись удалена');
                    navigate(`/book/${state.userBookId}`, { replace: true });
                  } catch (error) {
                    toastError(error);
                  }
                },
              }),
          }, 'Удалить запись')
        : null,
      h('div', { style: { height: '40px' } }),
      footerBar(h('div', { style: { flex: '1', display: 'flex' } }, saveButton)),
    );

    renderTags();
    validate();
    setTimeout(() => contentInput.focus(), 100);
  }
}
