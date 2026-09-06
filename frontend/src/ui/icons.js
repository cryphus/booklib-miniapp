/**
 * Icons copied verbatim from the design canvas (design/Remarka Mini App.dc.html).
 * Every path, stroke width and cap matches the mockups; only size/colour are parameters.
 */

import { svg } from './dom.js';

const wrap = (size, body, { stroke = '#14532D', width = 1.8, fill = 'none', extra = '' } = {}) =>
  svg(
    `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="${fill}" stroke="${stroke}"
      stroke-width="${width}" stroke-linecap="round" stroke-linejoin="round" ${extra}>${body}</svg>`,
  );

export const icons = {
  back: (size = 20, color = '#14532D') => wrap(size, '<path d="M14 6l-6 6 6 6"></path>', { stroke: color, width: 2 }),

  chevron: (size = 17, color = '#C2C7CD') =>
    wrap(size, '<path d="m9 5 7 7-7 7"></path>', { stroke: color, width: 2.2 }),

  plus: (size = 22, color = '#FFFFFF', width = 2.2) =>
    wrap(size, '<path d="M12 5v14M5 12h14"></path>', { stroke: color, width }),

  close: (size = 13, color = '#8A9099') =>
    wrap(size, '<path d="M6 6l12 12M18 6 6 18"></path>', { stroke: color, width: 3 }),

  search: (size = 20, color = '#A7ADB5') =>
    wrap(size, '<circle cx="11" cy="11" r="7"></circle><path d="M16.5 16.5 21 21"></path>', {
      stroke: color,
      width: 2,
    }),

  filters: (size = 21, color = '#14532D') =>
    wrap(
      size,
      '<path d="M4 7h10M18 7h2M4 17h4M12 17h8"></path><circle cx="16" cy="7" r="2"></circle><circle cx="10" cy="17" r="2"></circle>',
      { stroke: color },
    ),

  /** Outline bookmark; pass filled=true for the saved state. */
  bookmark: (size = 18, color = '#14532D', filled = false) =>
    wrap(size, '<path d="M7 4h10a1 1 0 0 1 1 1v15l-6-4-6 4V5a1 1 0 0 1 1-1z"></path>', {
      stroke: color,
      fill: filled ? color : 'none',
      width: filled ? 1.7 : 1.8,
    }),

  dots: (size = 18, color = '#8A9099') =>
    svg(
      `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="${color}"><circle cx="5" cy="12" r="1.7"></circle><circle cx="12" cy="12" r="1.7"></circle><circle cx="19" cy="12" r="1.7"></circle></svg>`,
    ),

  home: (size = 24, color = '#A7ADB5') =>
    wrap(size, '<path d="M4 10.5 12 4l8 6.5V20a1 1 0 0 1-1 1h-4v-6H9v6H5a1 1 0 0 1-1-1z"></path>', {
      stroke: color,
    }),

  user: (size = 24, color = '#A7ADB5') =>
    wrap(size, '<circle cx="12" cy="8" r="3.4"></circle><path d="M5 20c1.6-3.6 4-5 7-5s5.4 1.4 7 5"></path>', {
      stroke: color,
    }),

  note: (size = 16, color = '#027C41') =>
    wrap(size, '<path d="M6 4h8l4 4v12H6z"></path><path d="M9 12h6M9 16h4"></path>', { stroke: color }),

  chapter: (size = 15, color = '#A7ADB5') =>
    wrap(size, '<path d="M4 6h7v13H4zM13 6h7v13h-7z"></path>', { stroke: color }),

  star: (size = 28, color = '#027C41') =>
    wrap(size, '<path d="M12 4l2.4 5 5.6.8-4 4 1 5.6-5-2.7-5 2.7 1-5.6-4-4 5.6-.8z"></path>', {
      stroke: color,
      width: 1.7,
    }),

  /** Telegram Stars glyph (solid), as used on the Premium screens. */
  starSolid: (size = 19, color = '#027C41') =>
    svg(
      `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="${color}" style="vertical-align:-2px"><path d="M12 3.2l2.6 5.4 5.9.85-4.3 4.2 1.05 5.9L12 16.75 6.75 19.55 7.8 13.65 3.5 9.45l5.9-.85z"></path></svg>`,
    ),

  check: (size = 19, color = '#027C41', width = 2.6) =>
    wrap(size, '<path d="M5 12.5 10 17.5 19 7"></path>', { stroke: color, width }),

  settings: (size = 18, color = '#14532D') =>
    wrap(
      size,
      '<circle cx="12" cy="12" r="3"></circle><path d="M12 3v3M12 18v3M3 12h3M18 12h3M6 6l2 2M16 16l2 2M18 6l-2 2M8 16l-2 2"></path>',
      { stroke: color },
    ),

  support: (size = 18, color = '#14532D') =>
    wrap(size, '<path d="M5 5h14v10H9l-4 4z"></path>', { stroke: color }),

  info: (size = 18, color = '#14532D') =>
    svg(
      `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="${color}" stroke-width="1.8" stroke-linecap="round"><circle cx="12" cy="12" r="9"></circle><path d="M12 11v5"></path><circle cx="12" cy="8" r=".8" fill="${color}" stroke="none"></circle></svg>`,
    ),

  history: (size = 18, color = '#027C41') =>
    wrap(
      size,
      '<path d="M12 7v5l3 2"></path><path d="M20.5 12a8.5 8.5 0 1 1-2.6-6.1"></path><path d="M20.5 4v4h-4"></path>',
      { stroke: color, width: 1.9 },
    ),

  send: (size = 20, color = '#FFFFFF') =>
    svg(
      `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="${color}"><path d="M3 12 21 4l-7 8 7 8z"></path></svg>`,
    ),

  trash: (size = 18, color = '#D64545') =>
    wrap(size, '<path d="M5 7h14M9 7V5h6v2M7 7l1 13h8l1-13"></path><path d="M10 11v6M14 11v6"></path>', {
      stroke: color,
    }),

  edit: (size = 18, color = '#14532D') =>
    wrap(size, '<path d="M4 20h4l10-10-4-4L4 16z"></path><path d="M13.5 6.5 17.5 10.5"></path>', {
      stroke: color,
    }),

  share: (size = 19, color = '#14532D') =>
    wrap(size, '<path d="M12 16V4M8 8l4-4 4 4M5 15v4a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-4"></path>', {
      stroke: color,
      width: 1.9,
    }),

  library: (size = 20, color = '#027C41') =>
    wrap(size, '<path d="M4 5h6v14H4zM12 5h3v14h-3zM17 6l3 12"></path>', { stroke: color }),

  book: (size = 20, color = '#027C41') =>
    wrap(size, '<path d="M5 5a2 2 0 0 1 2-2h12v18H7a2 2 0 0 1-2-2z"></path><path d="M9 3v18"></path>', {
      stroke: color,
    }),

  upload: (size = 22, color = '#7E9B87') =>
    wrap(size, '<path d="M12 16V5M8 9l4-4 4 4"></path><path d="M5 15v3a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-3"></path>', {
      stroke: color,
    }),

  warning: (size = 26, color = '#D64545') =>
    wrap(size, '<path d="M12 4 2.5 20h19z"></path><path d="M12 10v4"></path><circle cx="12" cy="17" r=".9" fill="' + color + '" stroke="none"></circle>', {
      stroke: color,
    }),

  refresh: (size = 20, color = '#FFFFFF') =>
    wrap(size, '<path d="M20 12a8 8 0 1 1-2.4-5.7"></path><path d="M20 4v4h-4"></path>', {
      stroke: color,
      width: 2,
    }),

  sparkle: (size = 18, color = '#027C41') =>
    wrap(size, '<path d="M12 5v6M9 8h6M17 13v4M15 15h4M6 14v3M4.5 15.5h3"></path>', { stroke: color }),
};

/** The Remarka AI avatar: a white rounded "face" with two dots, on a green circle. */
export function aiAvatar(size = 34, background = '#027C41', dot = '#027C41') {
  const inner = Math.round(size * 0.53);
  const innerH = Math.round(size * 0.41);
  const dotSize = Math.max(3, Math.round(size * 0.09));
  return svg(`
    <div style="width:${size}px;height:${size}px;flex:0 0 auto;border-radius:50%;background:${background};display:flex;align-items:center;justify-content:center">
      <div style="width:${inner}px;height:${innerH}px;border-radius:${Math.round(size * 0.16)}px;background:#FFFFFF;display:flex;align-items:center;justify-content:center;gap:${Math.max(3, Math.round(size * 0.1))}px">
        <div style="width:${dotSize}px;height:${dotSize}px;border-radius:50%;background:${dot}"></div>
        <div style="width:${dotSize}px;height:${dotSize}px;border-radius:50%;background:${dot}"></div>
      </div>
    </div>`);
}

/** The inverse mark from screen 29: a green rounded face with white dots. */
export function aiMark(width = 30, height = 23, background = '#0A9A54') {
  return svg(
    `<div style="width:${width}px;height:${height}px;border-radius:8px;background:${background};display:flex;align-items:center;justify-content:center;gap:5px">
      <div style="width:5px;height:5px;border-radius:50%;background:#FFFFFF"></div>
      <div style="width:5px;height:5px;border-radius:50%;background:#FFFFFF"></div>
    </div>`,
  );
}

/** The quotation glyph used on quote cards. */
export function quoteGlyph(size = 30) {
  return svg(
    `<div style="width:${size}px;height:${size}px;flex:0 0 auto;border-radius:${Math.round(size / 3)}px;background:#EAF4EC;display:flex;align-items:flex-start;justify-content:center;font:700 ${Math.round(size * 0.66)}px/1.6 Georgia,serif;color:#027C41">&ldquo;</div>`,
  );
}
