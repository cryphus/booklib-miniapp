/** Screen 39 — support: contact links and a short FAQ. */

import { icons } from '../ui/icons.js';
import { h, fill } from '../ui/dom.js';
import { navigate } from '../router.js';
import { backHeader, listRow, screen, useTelegramBack } from '../ui/components.js';

const SUPPORT_USERNAME = (typeof window !== 'undefined' && window.REMARKA_SUPPORT_USERNAME) || 'remarka_support';

const FAQ = [
  {
    question: 'Как AI находит ответы?',
    answer: 'AI ищет только среди ваших цитат и заметок и всегда показывает записи-источники. Он не отвечает на вопросы, по которым в библиотеке ничего нет.',
  },
  {
    question: 'Что даёт Premium?',
    answer: 'Больше AI-запросов в месяц и расширенный контекст. Библиотека, цитаты и заметки не ограничены и на бесплатном тарифе.',
  },
  {
    question: 'Где хранятся мои записи?',
    answer: 'На серверах Remarka, в вашем аккаунте. Telegram используется только для входа и не получает содержимое библиотеки.',
  },
];

export function supportScreen({ query: search }) {
  const topic = search.get('topic');
  const body = h('div');
  const view = screen({ header: backHeader('Поддержка') }, body);
  view.__cleanup = useTelegramBack('/settings');

  const openChat = (subject) => {
    const url = `https://t.me/${SUPPORT_USERNAME}?text=${encodeURIComponent(subject)}`;
    const tg = window.Telegram && window.Telegram.WebApp;
    if (tg && tg.openTelegramLink) tg.openTelegramLink(url);
    else window.open(url, '_blank', 'noopener');
  };

  fill(body, 
    h('div', {
      style: {
        marginTop: '18px', background: '#FFFFFF', borderRadius: '20px',
        boxShadow: 'var(--rm-shadow-card)', overflow: 'hidden',
      },
    },
      listRow({
        icon: icons.support(),
        label: 'Написать в поддержку',
        onClick: () => openChat('Вопрос по Remarka: '),
      }),
      listRow({
        icon: icons.warning(18, '#14532D'),
        label: 'Сообщить об ошибке',
        onClick: () => openChat('Ошибка в Remarka: '),
        last: true,
      }),
    ),

    h('div.rm-section-label', { style: { marginTop: '24px' } }, 'Частые вопросы'),
    h('div', { style: { marginTop: '10px', display: 'flex', flexDirection: 'column', gap: '10px' } },
      ...FAQ.map(faqItem),
    ),

    h('div', {
      style: {
        marginTop: '22px', fontSize: '13px', lineHeight: '1.5',
        color: 'var(--rm-text-muted)', textAlign: 'center',
      },
    }, 'Обычно отвечаем в течение одного рабочего дня.'),
    h('div', { style: { height: '30px' } }),
  );

  if (topic === 'bug') setTimeout(() => openChat('Ошибка в Remarka: '), 200);
  return view;

  function faqItem({ question, answer }) {
    let open = false;
    const answerNode = h('div', {
      style: {
        marginTop: '8px', fontSize: '14px', lineHeight: '1.5',
        color: 'var(--rm-text-secondary)', display: 'none',
      },
    }, answer);

    const chevron = icons.chevron(16);
    const card = h('div', {
      style: { background: '#FFFFFF', borderRadius: '18px', boxShadow: 'var(--rm-shadow-card)', padding: '14px 16px' },
      onClick: () => {
        open = !open;
        answerNode.style.display = open ? 'block' : 'none';
        chevron.style.transform = open ? 'rotate(90deg)' : 'none';
      },
    },
      h('div', { style: { display: 'flex', alignItems: 'center', gap: '10px' } },
        h('div', { style: { flex: '1', fontSize: '15px', fontWeight: '600' } }, question),
        chevron,
      ),
      answerNode,
    );
    chevron.style.transition = 'transform .18s';
    return card;
  }
}

export { navigate };
