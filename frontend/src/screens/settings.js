/** Screen 36 — settings: theme, account, help, documents, version. */

import { api } from '../api/client.js';
import { navigate } from '../router.js';
import { getState, invalidate, keys, query } from '../store.js';
import { icons } from '../ui/icons.js';
import { h, fill } from '../ui/dom.js';
import {
  backHeader,
  listRow,
  screen,
  toast,
  toastError,
  useTelegramBack,
} from '../ui/components.js';

const APP_VERSION = '1.0.0';

const THEMES = [
  { key: 'system', label: 'Как в Telegram' },
  { key: 'light', label: 'Светлая' },
  { key: 'dark', label: 'Тёмная' },
];

export function settingsScreen() {
  const body = h('div');
  const view = screen({ header: backHeader('Настройки') }, body);
  view.__cleanup = useTelegramBack('/profile');

  let theme = (getState().me && getState().me.preferences && getState().me.preferences.theme) || 'system';

  api.getPreferences()
    .then((preferences) => { theme = preferences.theme || 'system'; render(); })
    .catch(() => render());

  render();
  return view;

  function applyTheme(value) {
    const resolved = value === 'system'
      ? (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.colorScheme) || 'light'
      : value;
    document.documentElement.setAttribute('data-rm-theme', resolved);
  }

  async function selectTheme(value) {
    const previous = theme;
    theme = value;
    applyTheme(value);
    render();
    try {
      await api.updatePreferences({ theme: value });
      invalidate(keys.me, keys.preferences);
      toast('Настройки сохранены');
    } catch (error) {
      theme = previous;
      applyTheme(previous);
      render();
      toastError(error);
    }
  }

  function render() {
    fill(body, 
      h('div.rm-section-label', { style: { marginTop: '18px' } }, 'Интерфейс'),
      h('div', {
        style: {
          marginTop: '10px', background: '#FFFFFF', borderRadius: '20px',
          boxShadow: 'var(--rm-shadow-card)', overflow: 'hidden',
        },
      },
        h('div', { style: { padding: '14px 16px 8px', fontSize: '15px', fontWeight: '700' } }, 'Тема'),
        ...THEMES.map((option, index) =>
          h('button', {
            style: {
              width: '100%', height: '52px', display: 'flex', alignItems: 'center',
              justifyContent: 'space-between', padding: '0 16px', border: 'none',
              borderTop: '1px solid var(--rm-surface-grey)',
              background: theme === option.key ? 'var(--rm-surface-tint)' : '#FFFFFF',
              fontSize: '16px', fontWeight: theme === option.key ? '600' : '400', textAlign: 'left',
            },
            onClick: () => selectTheme(option.key),
          },
            h('div', null, option.label),
            theme === option.key ? icons.check(18) : null,
          ),
        ),
      ),

      h('div.rm-section-label', { style: { marginTop: '22px' } }, 'Аккаунт'),
      card(
        listRow({ icon: icons.user(18, '#14532D'), label: 'Аккаунт', onClick: () => navigate('/account') }),
        listRow({
          icon: icons.trash(18),
          label: 'Удалить аккаунт',
          danger: true,
          onClick: () => navigate('/account?delete=1'),
          last: true,
        }),
      ),

      h('div.rm-section-label', { style: { marginTop: '22px' } }, 'Помощь'),
      card(
        listRow({ icon: icons.support(), label: 'Поддержка', onClick: () => navigate('/support') }),
        listRow({
          icon: icons.warning(18, '#14532D'),
          label: 'Сообщить об ошибке',
          onClick: () => navigate('/support?topic=bug'),
          last: true,
        }),
      ),

      h('div.rm-section-label', { style: { marginTop: '22px' } }, 'О приложении'),
      card(
        listRow({
          icon: icons.info(),
          label: 'Политика конфиденциальности',
          onClick: () => navigate('/legal/privacy'),
        }),
        listRow({
          icon: icons.info(),
          label: 'Пользовательское соглашение',
          onClick: () => navigate('/legal/terms'),
        }),
        listRow({ label: 'Версия', value: APP_VERSION, last: true }),
      ),
      h('div', { style: { height: '30px' } }),
    );
  }

  function card(...rows) {
    return h('div', {
      style: {
        marginTop: '10px', background: '#FFFFFF', borderRadius: '20px',
        boxShadow: 'var(--rm-shadow-card)', overflow: 'hidden',
      },
    }, rows);
  }
}

export { query };
