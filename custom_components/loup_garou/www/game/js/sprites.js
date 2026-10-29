// Pixel art drawn from character grids. Each character is one pixel; '.' is
// transparent. Lower-case letters are fixed colours, upper-case letters take
// a theme colour from CSS (see .px-H / .px-L in pixel.css).

const SVG = 'http://www.w3.org/2000/svg';

const COLORS = {
  k: '#1a1430', w: '#f4f1ff', y: '#ffd95e', o: '#8d8aa8', r: '#e8455a',
  g: '#4fbf73', p: '#ff7ab8', v: '#8a5cd6', n: '#8a5a32', s: '#f2c39b',
  b: '#4aa3ff', d: '#5b5675',
};

const WOLF = [
  'k.........k',
  'kk.......kk',
  'kokkkkkkkok',
  'koooooooook',
  'korooooorok',
  'koooooooook',
  '.kookkkook.',
  '..kowwwok..',
  '...kkkkk...',
];

export const SPRITES = {
  moon: [
    '....yyy...',
    '..yyyy....',
    '.yyyy.....',
    '.yyy......',
    'yyyy......',
    'yyyy......',
    '.yyy......',
    '.yyyy.....',
    '..yyyy....',
    '....yyy...',
  ],
  sun: [
    '....y....',
    '.y.....y.',
    '...yyy...',
    '..yyyyy..',
    'y.yyyyy.y',
    '..yyyyy..',
    '...yyy...',
    '.y.....y.',
    '....y....',
  ],
  skull: [
    '..wwwwwww..',
    '.wwwwwwwww.',
    '.wkkwwwkkw.',
    '.wkkwwwkkw.',
    '.wwwwkwwww.',
    '..wwwwwww..',
    '..w.w.w.w..',
  ],
  heart: [
    '.kk...kk.',
    'kppk.kppk',
    'kpppkpppk',
    'kpppppppk',
    '.kpppppk.',
    '..kpppk..',
    '...kpk...',
    '....k....',
  ],
  potion_heal: [
    '...kkk...',
    '....n....',
    '...kgk...',
    '..kgggk..',
    '.kgggggk.',
    '.kgwgggk.',
    '..kkkkk..',
  ],
  potion_poison: [
    '...kkk...',
    '....n....',
    '...kvk...',
    '..kvvvk..',
    '.kvvvvvk.',
    '.kvwvvvk.',
    '..kkkkk..',
  ],
  cross: [
    'ww...ww',
    'www.www',
    '.wwwww.',
    '..www..',
    '.wwwww.',
    'www.www',
    'ww...ww',
  ],
  plus: [
    '..www..',
    '..www..',
    'wwwwwww',
    'wwwwwww',
    'wwwwwww',
    '..www..',
    '..www..',
  ],
  minus: [
    '.......',
    '.......',
    'wwwwwww',
    'wwwwwww',
    'wwwwwww',
    '.......',
    '.......',
  ],
  // Roles
  villager: [
    '...nnnnn...',
    '..nnnnnnn..',
    '...sssss...',
    '...sksks...',
    '...sssss...',
    '....sss....',
    '..ggggggg..',
    '.ggggggggg.',
    '.ggggggggg.',
  ],
  werewolf: WOLF,
  alpha_wolf: ['..y.y.y.y..', '..yyyyyyy..', ...WOLF],
  seer: [
    '...kkkkk...',
    '.kkwwwwwkk.',
    'kwwwvvvwwwk',
    'kwwvvkvvwwk',
    'kwwwvvvwwwk',
    '.kkwwwwwkk.',
    '...kkkkk...',
  ],
  witch: [
    '.....k.....',
    '....kvk....',
    '....kvvk...',
    '...kvvvk...',
    '...kvvvvk..',
    '..kvvvvvk..',
    '..kyyyyyk..',
    'kkkkkkkkkkk',
    '.kvvvvvvvk.',
  ],
  hunter: [
    '.....r.....',
    '...rrrrr...',
    '..r..r..r..',
    '.r...r...r.',
    '.r.......r.',
    'rrr..r..rrr',
    '.r.......r.',
    '.r...r...r.',
    '..r..r..r..',
    '...rrrrr...',
    '.....r.....',
  ],
  cupid: [
    '.kk...kk.',
    'kppk.kppk',
    'kpppkpppk',
    'kpppppppk',
    '.kpppppk.',
    '..kpppk..',
    '...kpk...',
    '....k....',
  ],
  elder: [
    '...ooooo...',
    '..ooooooo..',
    '..sksssks..',
    '..sssssss..',
    '..wwwwwww..',
    '...wwwww...',
    '....www....',
  ],
  scapegoat: [
    'kk.......kk',
    '.kk.....kk.',
    '..kwwwwwk..',
    '.wwwwwwwww.',
    '..wkwwwkw..',
    '..wwwwwww..',
    '...wwwww...',
    '....www....',
    '....nnn....',
    '.....n.....',
  ],
  little_girl: [
    '..pp...pp..',
    '..ppp.ppp..',
    '...pnnnp...',
    '..nnnnnnn..',
    '..nsssssn..',
    '..nsksksn..',
    '..nsssssn..',
    '..n.sss.n..',
    '....ppp....',
    '...ppppp...',
  ],
  minion: [
    '.rrrrrrrrr.',
    'rrrrrrrrrrr',
    'rr..rrr..rr',
    'rrr.rrr.rrr',
    '.rrrr.rrrr.',
    '..rr...rr..',
  ],
  sheriff: [
    '.....y.....',
    '....yyy....',
    '....yyy....',
    'yyyyyyyyyyy',
    '.yyyyyyyyy.',
    '..yyyyyyy..',
    '..yyyyyyy..',
    '.yyyy.yyyy.',
    '.yyy...yyy.',
    '.y.......y.',
  ],
};

function draw(rows, scale, palette = {}) {
  const w = Math.max(...rows.map(r => r.length));
  const svg = document.createElementNS(SVG, 'svg');
  svg.setAttribute('viewBox', `0 0 ${w} ${rows.length}`);
  svg.setAttribute('width', w * scale);
  svg.setAttribute('height', rows.length * scale);
  svg.setAttribute('shape-rendering', 'crispEdges');
  svg.setAttribute('aria-hidden', 'true');
  svg.setAttribute('focusable', 'false');
  svg.classList.add('sprite');
  rows.forEach((row, y) => {
    // One rect per horizontal run of the same colour keeps the DOM small.
    for (let x = 0; x < row.length;) {
      const c = row[x];
      let end = x + 1;
      while (end < row.length && row[end] === c) end++;
      if (c !== '.') {
        const rect = document.createElementNS(SVG, 'rect');
        rect.setAttribute('x', x);
        rect.setAttribute('y', y);
        rect.setAttribute('width', end - x);
        rect.setAttribute('height', 1);
        if (c >= 'A' && c <= 'Z') rect.setAttribute('class', `px-${c}`);
        else rect.setAttribute('fill', palette[c] || COLORS[c] || COLORS.k);
        svg.appendChild(rect);
      }
      x = end;
    }
  });
  return svg;
}

export function sprite(name, scale = 4) {
  return draw(SPRITES[name] || SPRITES.villager, scale);
}

// ── Player avatars ───────────────────────────────────────────────────────────
// Each name always draws the same face, so players spot themselves at a glance.

const AVATARS = [
  ['..hhhh..', '.hhhhhh.', '.hssssh.', '.skssks.', '.ssssss.', '..smms..', '.cccccc.', 'cccccccc'],
  ['.hhhhhh.', 'hhhhhhhh', 'hhsssshh', 'hskssksh', 'hssssssh', 'h.smms.h', '.cccccc.', 'cccccccc'],
  ['..h..h..', '.hhhhhh.', '.ssssss.', '.skssks.', '.ssssss.', '..smms..', '.cccccc.', 'cccccccc'],
];
const HAIR = ['#3b2a20', '#8a5a32', '#e0b04a', '#c4532d', '#1a1430', '#d9d4e8'];
const SKIN = ['#f2c39b', '#d99a6c', '#a86b45', '#6e4630'];
const SHIRT = ['#4fbf73', '#4aa3ff', '#e8455a', '#8a5cd6', '#ffb347', '#2fb6b0'];

function hash(text) {
  let n = 2166136261;
  for (const ch of text.toLowerCase()) n = Math.imul(n ^ ch.codePointAt(0), 16777619);
  return n >>> 0;
}

export function avatar(name, scale = 4) {
  const n = hash(name || '?');
  return draw(AVATARS[n % AVATARS.length], scale, {
    h: HAIR[(n >>> 4) % HAIR.length],
    s: SKIN[(n >>> 8) % SKIN.length],
    c: SHIRT[(n >>> 12) % SHIRT.length],
    m: '#7a3b3b',
  });
}

// ── Scenery ──────────────────────────────────────────────────────────────────

function seeded(seed) {
  let s = seed;
  return () => ((s = Math.imul(s ^ (s >>> 15), 2246822507) + 0x6d2b79f5 >>> 0) / 4294967296);
}

// Rooftops along the bottom of the screen: H = hill/house, L = lit window.
export function skyline(width = 200, height = 20) {
  const rnd = seeded(7);
  const grid = Array.from({ length: height }, () => Array(width).fill('.'));
  const fill = (x, y, c) => { if (x >= 0 && x < width && y >= 0 && y < height) grid[y][x] = c; };
  for (let x = 0; x < width; x++) {
    // Rolling hill
    const top = height - 4 - Math.round(1.5 + 1.5 * Math.sin(x / 17));
    for (let y = top; y < height; y++) fill(x, y, 'H');
  }
  for (let x = 2; x < width - 8;) {
    const w = 7 + Math.floor(rnd() * 6);
    const wall = 4 + Math.floor(rnd() * 5);
    const base = height - 3;
    for (let y = base - wall; y < base; y++) for (let i = 0; i < w; i++) fill(x + i, y, 'H');
    const roof = Math.ceil(w / 2);
    for (let r = 1; r <= roof; r++) for (let i = r - 1; i <= w - r; i++) fill(x + i, base - wall - r, 'H');
    // Two lit windows per house, sometimes one.
    const wy = base - wall + 1;
    fill(x + 1, wy, 'L'); fill(x + 2, wy, 'L');
    if (rnd() > 0.35) { fill(x + w - 3, wy, 'L'); fill(x + w - 2, wy, 'L'); }
    x += w + 3 + Math.floor(rnd() * 10);
  }
  const svg = draw(grid.map(r => r.join('')), 1);
  svg.removeAttribute('width');
  svg.removeAttribute('height');
  svg.setAttribute('preserveAspectRatio', 'xMidYMax slice');
  return svg;
}

// Box-shadow list of 4px stars for the night sky.
export function starField(count = 28) {
  const rnd = seeded(42);
  return Array.from({ length: count }, () => {
    const x = Math.floor(rnd() * 100);
    const y = Math.floor(rnd() * 60);
    return `${x}vw ${y}vh 0 0 var(--star)`;
  }).join(',');
}
