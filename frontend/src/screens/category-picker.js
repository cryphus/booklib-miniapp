/** Bottom sheet for creating or choosing a category (the "+ Новая" chip). */

import { h } from '../ui/dom.js';
import { openSheet } from '../ui/components.js';

export function categoryPicker({ current = null, onPick }) {
  let value = current || '';

  const input = h('input', {
    value,
    placeholder: 'Например, Психология',
    maxlength: '64',
    style: { fontSize: '16px' },
    onInput: (event) => { value = event.target.value; submit.disabled = !value.trim(); },
    onKeydown: (event) => { if (event.key === 'Enter') confirm(); },
  });

  const submit = h('button.rm-btn', { onClick: () => confirm(), disabled: !value.trim() }, 'Готово');

  const sheet = openSheet({ title: 'Новая категория', subtitle: 'Категория видна только вам' },
    h('div', { style: { marginTop: '18px' } },
      h('div.rm-input', null, input),
      h('div', { style: { marginTop: '18px' } }, submit),
    ),
  );

  function confirm() {
    const name = value.trim();
    if (!name) return;
    sheet.close();
    onPick(name);
  }

  setTimeout(() => input.focus(), 120);
  return sheet;
}
