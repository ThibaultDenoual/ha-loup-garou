import { translate, translateAttr } from './i18n.js';

// Builds DOM nodes directly (no HTML parsing), so player names can never
// become markup.
//
//   h('button', { class: 'btn', i18n: 'ui.night.skip', on: { click } })
//   h('span', { text: player.name })
//   h('div', { i18n: ['ui.vote.progress', { done, total }] }, child, ...)
//
// Props: class, text (raw), i18n / i18nLabel / i18nPlaceholder (key or
// [key, vars]), on (event map), data (dataset), anything else → attribute.
export function h(tag, props = {}, ...children) {
  const el = document.createElement(tag);
  for (const [name, value] of Object.entries(props)) {
    if (value == null || value === false) continue;
    switch (name) {
      case 'class': el.className = value; break;
      case 'text': el.textContent = value; break;
      case 'i18n': translate(el, ...asKey(value)); break;
      case 'i18nLabel': translateAttr(el, 'aria-label', ...asKey(value)); break;
      case 'i18nPlaceholder': translateAttr(el, 'placeholder', ...asKey(value)); break;
      case 'on': for (const [ev, fn] of Object.entries(value)) el.addEventListener(ev, fn); break;
      case 'data': Object.assign(el.dataset, value); break;
      default: el.setAttribute(name, value === true ? '' : value);
    }
  }
  el.append(...children.flat().filter(c => c != null && c !== false));
  return el;
}

function asKey(value) {
  return Array.isArray(value) ? value : [value];
}

export const $ = id => document.getElementById(id);

export function show(el, visible) {
  el.hidden = !visible;
}
