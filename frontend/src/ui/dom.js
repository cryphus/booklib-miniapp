/** Minimal hyperscript helpers. Keeps screen code declarative without a framework. */

/**
 * @param {string} tag  'div', 'div.rm-card', 'button.rm-btn'
 * @param {object|null} [props] attributes; `style` object, `on*` handlers, `dataset`
 * @param {...(Node|string|number|false|null|undefined|Array)} children
 */
export function h(tag, props, ...children) {
  const [name, ...classes] = tag.split('.');
  const el = document.createElement(name || 'div');
  if (classes.length) el.className = classes.join(' ');

  if (props && typeof props === 'object' && !(props instanceof Node) && !Array.isArray(props)) {
    for (const [key, value] of Object.entries(props)) {
      if (value === null || value === undefined || value === false) continue;
      if (key === 'style' && typeof value === 'object') {
        Object.assign(el.style, value);
      } else if (key === 'class' || key === 'className') {
        el.className = el.className ? `${el.className} ${value}` : String(value);
      } else if (key === 'dataset') {
        Object.assign(el.dataset, value);
      } else if (key.startsWith('on') && typeof value === 'function') {
        el.addEventListener(key.slice(2).toLowerCase(), value);
      } else if (key === 'html') {
        el.innerHTML = value;
      } else if (key === 'ref' && typeof value === 'function') {
        value(el);
      } else if (key in el && key !== 'list' && typeof value !== 'object') {
        el[key] = value;
      } else {
        el.setAttribute(key, String(value));
      }
    }
  } else if (props !== undefined && props !== null) {
    children.unshift(props);
  }

  append(el, children);
  return el;
}

export function append(parent, children) {
  for (const child of children.flat(Infinity)) {
    if (child === null || child === undefined || child === false || child === true) continue;
    parent.appendChild(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return parent;
}

/** Inline SVG from the design canvas markup. */
export function svg(markup) {
  const wrapper = document.createElement('div');
  wrapper.innerHTML = markup.trim();
  return wrapper.firstElementChild;
}

export function clear(node) {
  while (node.firstChild) node.removeChild(node.firstChild);
  return node;
}

/**
 * Replaces a node's children, skipping null/undefined/false.
 * Native replaceChildren() stringifies those into literal "null" text nodes.
 */
export function fill(node, ...children) {
  clear(node);
  append(node, children);
  return node;
}

export function mount(node, ...children) {
  clear(node);
  append(node, children);
  return node;
}

/** Escapes text before it goes anywhere near innerHTML. */
export function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

/** Renders `text` with every occurrence of `query` wrapped in a highlight mark. */
export function highlight(text, query) {
  const el = document.createElement('span');
  const source = String(text ?? '');
  const needle = String(query ?? '').trim();
  if (!needle) {
    el.textContent = source;
    return el;
  }
  const lowerSource = source.toLowerCase();
  const lowerNeedle = needle.toLowerCase();
  let index = 0;
  let found = lowerSource.indexOf(lowerNeedle);
  if (found === -1) {
    el.textContent = source;
    return el;
  }
  while (found !== -1) {
    el.appendChild(document.createTextNode(source.slice(index, found)));
    const mark = document.createElement('span');
    mark.className = 'rm-mark';
    mark.textContent = source.slice(found, found + needle.length);
    el.appendChild(mark);
    index = found + needle.length;
    found = lowerSource.indexOf(lowerNeedle, index);
  }
  el.appendChild(document.createTextNode(source.slice(index)));
  return el;
}

/** Trailing-edge debounce for search inputs. */
export function debounce(fn, wait = 300) {
  let timer = null;
  const wrapped = (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), wait);
  };
  wrapped.cancel = () => clearTimeout(timer);
  return wrapped;
}
