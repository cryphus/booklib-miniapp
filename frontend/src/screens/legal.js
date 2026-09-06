/**
 * Screens 40–41 — legal documents, served by the backend.
 *
 * The backend marks these as drafts; the banner below says so plainly rather than
 * presenting the text as a finished policy.
 */

import { api } from '../api/client.js';
import { icons } from '../ui/icons.js';
import { h, fill } from '../ui/dom.js';
import {
  backHeader,
  errorState,
  screen,
  skeletonBlock,
  useTelegramBack,
  logError,
} from '../ui/components.js';

const TITLES = {
  privacy: 'Политика конфиденциальности',
  terms: 'Пользовательское соглашение',
  about: 'О приложении',
};

export function legalScreen({ params }) {
  const slug = params.slug;
  const body = h('div');
  const view = screen({ header: backHeader(TITLES[slug] || 'Документ') }, body);
  view.__cleanup = useTelegramBack('/settings');

  if (slug === 'about') renderAbout();
  else load();

  return view;

  async function load() {
    fill(body, 
      skeletonBlock('16px', '6px', { marginTop: '20px', width: '40%' }),
      skeletonBlock('80px', '14px', { marginTop: '18px' }),
      skeletonBlock('80px', '14px', { marginTop: '14px' }),
    );
    try {
      const document_ = await api.getLegalDocument(slug);
      render(document_);
    } catch (error) {
      fill(body, errorState({ title: 'Не удалось загрузить документ', onRetry: load }));
      logError('legal', error);
    }
  }

  function render(document_) {
    fill(body, 
      document_.updated_at
        ? h('div', { style: { marginTop: '16px', fontSize: '13px', color: 'var(--rm-text-muted)' } },
            `Обновлено ${document_.updated_at}`)
        : null,
      document_.is_placeholder
        ? h('div', {
            style: {
              marginTop: '16px', borderRadius: '16px', background: 'var(--rm-surface-soft)',
              padding: '14px 16px', display: 'flex', gap: '10px', alignItems: 'flex-start',
            },
          },
            icons.info(18),
            h('div', { style: { fontSize: '13px', lineHeight: '1.5', color: 'var(--rm-green-dark)' } },
              'Черновик. Итоговый юридический текст будет добавлен перед публичным релизом.'),
          )
        : null,
      h('div', {
        style: {
          marginTop: '18px', fontSize: '15px', lineHeight: '1.6', color: 'var(--rm-text)',
          whiteSpace: 'pre-wrap',
        },
      }, document_.content),
      h('div', { style: { height: '30px' } }),
    );
  }

  function renderAbout() {
    fill(body, 
      h('div', { style: { paddingTop: '24px', textAlign: 'center' } },
        h('div', {
          style: {
            width: '72px', height: '72px', margin: '0 auto', borderRadius: '24px',
            background: 'var(--rm-green)', display: 'flex', alignItems: 'center',
            justifyContent: 'center',
          },
        }, icons.book(32, '#FFFFFF')),
        h('div', { style: { marginTop: '16px', fontSize: '24px', fontWeight: '800', color: 'var(--rm-green-dark)' } },
          'Remarka'),
        h('div', { style: { marginTop: '6px', fontSize: '15px', color: 'var(--rm-text-muted)' } },
          'Твоя библиотека мыслей · 1.0.0'),
        h('div', {
          style: {
            marginTop: '20px', fontSize: '15px', lineHeight: '1.6',
            color: 'var(--rm-text-secondary)', textAlign: 'left',
          },
        }, 'Remarka хранит ваши книги, цитаты и собственные мысли, а Remarka AI отвечает на вопросы только по этим записям и всегда показывает источники.'),
      ),
    );
  }
}
