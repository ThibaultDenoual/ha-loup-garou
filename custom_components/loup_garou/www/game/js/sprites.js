// Pixel art drawn from character grids. Each character is one pixel; '.' is
// transparent. Lower-case letters are fixed colours, upper-case letters take
// a theme colour from CSS (see .px-H / .px-F / .px-L in pixel.css).
//
// Drawings are shaded and lit from the top left, like the frames in
// pixel.css. Symmetric drawings are written as their left half.

const SVG = 'http://www.w3.org/2000/svg';

const COLORS = {
  k: '#15112e', e: '#46416e', o: '#7c77a6', l: '#b7b2d8', w: '#ece9fa', i: '#a9a4c8',
  y: '#ffd95e', a: '#d9a23a', g: '#fff3b8',
  r: '#e8455a', d: '#9e2a3c', p: '#ff7ab8', m: '#ffc2dc', z: '#c74386', q: '#c75b7f',
  v: '#8a5cd6', u: '#5b3799', c: '#4aa3ff', j: '#bfe6ff',
  f: '#4fbf73', h: '#2f7d46', n: '#7a4a2a', b: '#b07a45',
  s: '#f2c39b', t: '#c98e6b',
};

const mirror = half => half.map(r => r + [...r].reverse().join(''));

// Build a grid from paint(x, y) → colour letter or '.'.
function paint(width, height, fn) {
  return Array.from({ length: height }, (_, y) =>
    Array.from({ length: width }, (_, x) => fn(x, y)).join(''));
}

// Surround every painted shape with a one-pixel dark outline.
function outlined(rows) {
  const h = rows.length + 2;
  const w = rows[0].length + 2;
  const at = (x, y) => (rows[y - 1] || '')[x - 1] || '.';
  return paint(w, h, (x, y) => {
    if (at(x, y) !== '.') return at(x, y);
    for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
      if (at(x + dx, y + dy) !== '.') return 'k';
    }
    return '.';
  });
}

// ── Celestial ────────────────────────────────────────────────────────────────

const MOON = paint(14, 14, (x, y) => {
  const c = 6.5;
  if (Math.hypot(x - c, y - c) > c + 0.3) return '.';
  const bite = Math.hypot(x - (c + 4.2), y - (c - 3.2));
  if (bite <= c - 0.6) return '.';
  if (bite <= c + 0.8) return 'a';
  return x + y < c ? 'g' : 'y';
});

const FULL_MOON = paint(30, 30, (x, y) => {
  const c = 14.5;
  const d = Math.hypot(x - c, y - c);
  if (d > c + 0.3) return '.';
  if (d > c - 1.2 || x + y > 2 * c + 14) return 'a';
  const crater = Math.hypot(x - 9, y - 11) < 3.2 || Math.hypot(x - 19, y - 20) < 2.4 || Math.hypot(x - 20, y - 8) < 1.8;
  return crater ? 'y' : 'g';
});

const SUN = paint(15, 15, (x, y) => {
  const c = 7;
  const d = Math.hypot(x - c, y - c);
  const ray = (x === c || y === c || Math.abs(x - c) === Math.abs(y - c)) && d >= 5.6 && d <= 7.3;
  if (d <= 3.7) return d > 2.8 ? 'a' : (x < c && y < c ? 'g' : 'y');
  return ray ? 'y' : '.';
});

// ── Roles ────────────────────────────────────────────────────────────────────

const WOLF = mirror([
  '.k..........',
  '.kk.........',
  '.kek........',
  '.kepk.......',
  '.kepek......',
  '.keqqek.....',
  '.keqqeekkkkk',
  '.keqqeeooooo',
  '.keeeoooooll',
  'kkeooooooolw',
  'keooooooooll',
  'keookkkooooo',
  'keooyykooool',
  'keeoooooooll',
  'kkeeoooollll',
  '.kkeeooollll',
  '..kkeeolllll',
  '....kkelllll',
  '......klllll',
  '......kllkkk',
  '.......kllkk',
  '.......klllk',
  '........kwlk',
  '.........kkk',
]);

// The alpha wears a crown between its ears.
const ALPHA = (() => {
  const crown = { 2: 'y..y.', 3: 'yy.yy', 4: 'ayyyy', 5: 'aaaaa' };
  return WOLF.map((row, y) => {
    if (!crown[y]) return row;
    const half = crown[y];
    const band = half + [...half].reverse().join('');
    return row.slice(0, 7) + band + row.slice(17);
  });
})();

const VILLAGER = mirror([
  '.......kkk',
  '.....kkaay',
  '....kayyyy',
  '....kayyyy',
  '.kkkkaaaaa',
  'kaayyyyyyy',
  '.kkkkkkkkk',
  '...ktsssss',
  '...ktsksss',
  '...ktsksss',
  '...kttssss',
  '....ktsssn',
  '.....kttss',
  '...khhffff',
  '..khffffff',
  '.khhffffff',
  '.khhffffff',
  '.kkkkkkkkk',
]);

// A crystal ball with an eye inside, on a wooden stand.
const SEER = (() => {
  const ball = paint(20, 18, (x, y) => {
    const d = Math.hypot(x - 9.5, y - 8.5);
    if (d > 8.6) return '.';
    if (Math.hypot(x - 6, y - 5) < 1.6) return 'w';
    const eye = Math.abs(y - 9) <= 2.4 - Math.abs(x - 9.5) * 0.42;
    if (eye) {
      const iris = Math.hypot(x - 9.5, y - 9);
      return iris < 1 ? 'k' : iris < 2.3 ? 'v' : 'w';
    }
    return d > 6.8 || x + y > 24 ? 'u' : x + y < 12 ? 'j' : 'c';
  });
  const stand = ['....nbbbbbbbbbbn....', '...nbbbbbbbbbbbbn...', '..nnnnnnnnnnnnnnnn..'];
  return outlined([...ball, ...stand]);
})();

const WITCH = mirror([
  '..........k',
  '.........kv',
  '.........kv',
  '........kvv',
  '........kuv',
  '.......kuvv',
  '.......kuvv',
  '......kuvvv',
  '......kuvvv',
  '.....kuuvvv',
  '.....kaaaaa',
  '.....kaaayy',
  '.kkkkuuuuvv',
  'kuuuuuvvvvv',
  '.kkkkkkkkkk',
]);

// A crosshair, lit on its upper left.
const HUNTER = outlined(paint(21, 21, (x, y) => {
  const c = 10;
  const d = Math.hypot(x - c, y - c);
  const tick = (x === c || y === c) && (d >= 3 && d <= 5.2 || d >= 8.6);
  if ((d >= 6.4 && d <= 8.4) || tick) return x + y > 2 * c + 3 ? 'd' : 'r';
  return d <= 1 ? 'r' : '.';
}));

function heart(arrow) {
  const body = paint(20, 18, (x, y) => {
    const u = (x - 9.5) / 8;
    const v = 1.3 - y * 0.138;
    const inside = (u * u + v * v - 1) ** 3 - u * u * v ** 3 <= 0;
    if (!inside) return '.';
    if (Math.hypot(x - 5, y - 4) < 1.8) return 'm';
    return x + y > 21 ? 'z' : 'p';
  });
  const rows = outlined(body).map(r => [...r]);
  if (arrow) {
    for (let i = 0; i < 20; i++) {
      const x = 1 + i;
      const y = 19 - i;
      if (rows[y] && rows[y][x] !== undefined) rows[y][x] = i < 3 ? 'w' : 'n';
    }
    for (const [x, y] of [[19, 1], [20, 1], [20, 2], [18, 0], [21, 2]]) if (rows[y] && rows[y][x] !== undefined) rows[y][x] = 'y';
  }
  return rows.map(r => r.join(''));
}

const ELDER = mirror([
  '......kkkk',
  '....kktsss',
  '...kisssss',
  '..kiisssss',
  '..kiisssss',
  '..kitwwwss',
  '..kitsksss',
  '..kitsssss',
  '..kitsssst',
  '..kiwwwwww',
  '..kwwwwlww',
  '..kwwwwwww',
  '...kwwwlww',
  '....kwwwww',
  '.....kkwww',
  '.......kkk',
]);

const SCAPEGOAT = mirror([
  'kk........',
  'kbk.......',
  'kbbk......',
  '.kbbk.....',
  '..kbbk.kkk',
  '...kbkkwww',
  'kk..kklwww',
  'kllkklwwww',
  '.kkklwwwww',
  '....klykww',
  '....klwwww',
  '.....klwww',
  '.....klwww',
  '.....klwqq',
  '......klww',
  '......klwl',
  '.......klw',
  '........kl',
]);

// Little Red Riding Hood: the girl who spies on the wolves.
const LITTLE_GIRL = mirror([
  '......kkkk',
  '....kkdrrr',
  '...kdrrrrr',
  '..kdrrrrrr',
  '..kdrrnnnn',
  '.kdrnnnnss',
  '.kdrnsssss',
  '.kdrnsksss',
  '.kdrnsksss',
  '.kdrnsssss',
  '.kdrrtsssn',
  '.kddrrttss',
  'kddrrrkkkk',
  'kdrrrrrrrr',
  'kdrrrrrrry',
  'kddrrrrrrr',
  'kkkkkkkkkk',
]);

// A hooded follower of the wolves, eyes glowing red.
const MINION = mirror([
  '......kkkk',
  '....kkuvvv',
  '...kuuvvvv',
  '..kuuvvvvv',
  '..kuvvkkkk',
  '.kuuvkkkkk',
  '.kuuvkkrkk',
  '.kuuvkkkkk',
  '.kuuvvkkkk',
  'kuuuvvvvkk',
  'kuuuvvvvvv',
  'kuuuvvvvvv',
  'kuuvvvvvvv',
  'kuuvvvvvvy',
  'kkkkkkkkkk',
]);

// Six-pointed tin star with round tips.
const STAR = Array.from({ length: 12 }, (_, i) => {
  const a = i * Math.PI / 6 - Math.PI / 2;
  const r = i % 2 ? 4.6 : 8.4;
  return [10 + r * Math.cos(a), 10 + r * Math.sin(a)];
});
function inPolygon(x, y, pts) {
  let inside = false;
  for (let i = 0, j = pts.length - 1; i < pts.length; j = i++) {
    const [xi, yi] = pts[i];
    const [xj, yj] = pts[j];
    if ((yi > y) !== (yj > y) && x < (xj - xi) * (y - yi) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}
const SHERIFF = outlined(paint(21, 21, (x, y) => {
  const tip = STAR.some(([px, py], i) => i % 2 === 0 && Math.hypot(x - px, y - py) < 1.7);
  if (!inPolygon(x + 0.5, y + 0.5, STAR) && !tip) return '.';
  const d = Math.hypot(x - 10, y - 10);
  if (d < 2.6) return d < 1.5 ? 'y' : 'a';
  return x + y > 22 ? 'a' : x + y < 15 ? 'g' : 'y';
}));

const SKULL = mirror([
  '...iiii',
  '..iwwww',
  '.iwwwww',
  '.iwwwww',
  '.iwkkkw',
  '.iwkkkw',
  '.iiwwwk',
  '..iwwww',
  '...iwiw',
  '...iiii',
]);

const FLASK = mirror([
  '....kkk',
  '....knn',
  '....kkk',
  '.....kl',
  '.....kl',
  '...kkll',
  '..klfff',
  '.klffff',
  'klwffff',
  'klwffff',
  'klfffff',
  'khfffff',
  '.khffff',
  '..kkkkk',
]);
const POISON = FLASK.map(r => r.replace(/f/g, 'v').replace(/h/g, 'u'));

// ── Icons (drawn at small scales) ───────────────────────────────────────────

const ICONS = {
  cross: ['ww...ww', 'www.www', '.wwwww.', '..www..', '.wwwww.', 'www.www', 'ww...ww'],
  plus: ['..www..', '..www..', 'wwwwwww', 'wwwwwww', 'wwwwwww', '..www..', '..www..'],
  minus: ['.......', '.......', 'wwwwwww', 'wwwwwww', 'wwwwwww', '.......', '.......'],
  door: ['.kkkkkk.', '.kwwwwk.', '.kwwwwk.', '.kwwwwk.', '.kwwkwk.', '.kwwwwk.', '.kwwwwk.', 'kkkkkkkk'],
  tick: ['......w', '.....ww', 'w...ww.', 'ww.ww..', '.www...', '..w....'],
};

export const SPRITES = {
  moon: MOON, full_moon: FULL_MOON, sun: SUN, skull: SKULL,
  heart: heart(false), potion_heal: FLASK, potion_poison: POISON,
  ...ICONS,
  villager: VILLAGER, werewolf: WOLF, alpha_wolf: ALPHA, seer: SEER, witch: WITCH,
  hunter: HUNTER, cupid: heart(true), elder: ELDER, scapegoat: SCAPEGOAT,
  little_girl: LITTLE_GIRL, minion: MINION, sheriff: SHERIFF,
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

export function sprite(name, scale = 2) {
  return draw(SPRITES[name] || SPRITES.villager, scale);
}

// ── Player avatars ───────────────────────────────────────────────────────────
// Each name always draws the same face, so players spot themselves at a glance.

const FACE = ['jtsksss', 'jtsksss', '.tsssss', '.tsqsss', '..tsssm', '...tsss', '..dcccc', '.dccccc'];
const AVATARS = [
  mirror(['....jjj', '..jjhhh', '.jhhhhu', '.jhhhhh', 'jhhjsss', 'jhtssss', ...FACE]),
  mirror(['....jjj', '..jjhhh', '.jhhhhu', 'jhhhhhh', 'jhhjsss', 'jhtssss', 'jhtksss', 'jhtksss',
    'jhtssss', 'jhtqsss', 'jh.tssm', 'jj..tss', '.jdcccc', 'jdccccc']),
  mirror(['.j...j.', '.jj.jjh', '.jhhhhu', '.jhhhhh', 'jhhjsss', 'jhtssss', ...FACE]),
];
const HAIR = ['#4a3226', '#9a6436', '#e8b84e', '#c9572f', '#2a2140', '#dcd6ec'];
const SKIN = ['#f4c8a0', '#dc9c6c', '#ad6d45', '#734a31'];
const SHIRT = ['#4fbf73', '#4aa3ff', '#e8455a', '#9466dc', '#ffb347', '#2fb6b0'];

const mix = (hex, to, f) => {
  const a = parseInt(hex.slice(1), 16);
  const b = parseInt(to.slice(1), 16);
  const ch = s => Math.round(((a >> s) & 255) * (1 - f) + ((b >> s) & 255) * f);
  return `#${((1 << 24) | (ch(16) << 16) | (ch(8) << 8) | ch(0)).toString(16).slice(1)}`;
};

function hash(text) {
  let n = 2166136261;
  for (const ch of text.toLowerCase()) n = Math.imul(n ^ ch.codePointAt(0), 16777619);
  return n >>> 0;
}

export function avatar(name, scale = 3) {
  const n = hash(name || '?');
  const hair = HAIR[(n >>> 4) % HAIR.length];
  const skin = SKIN[(n >>> 8) % SKIN.length];
  const shirt = SHIRT[(n >>> 12) % SHIRT.length];
  return draw(AVATARS[n % AVATARS.length], scale, {
    h: hair, j: mix(hair, COLORS.k, 0.45), u: mix(hair, '#ffffff', 0.35),
    s: skin, t: mix(skin, '#6b2f3a', 0.3), q: mix(skin, COLORS.r, 0.35), m: '#7a3b3b',
    c: shirt, d: mix(shirt, COLORS.k, 0.35),
  });
}

// ── Village trades ───────────────────────────────────────────────────────────
// Each public role (public_roles.py) has its own portrait: the headwear and
// outfit say the trade, while hair and skin still follow the player's name.
// Letters x/z are the trade's own colours; c/d its outfit.

const FOREHEAD = ['jhhjsss', 'jhtssss'];
const BEARD = ['jtsksss', 'jtsksss', '.tsssss', '.tsqsss', '..thhhh', '...hhhh', '..dhhhh', '.dccccc'];
// Six rows of headwear, the forehead, then the face; outlined like the roles.
const TRADES = {
  baker: {        // tall pleated toque
    rows: ['..lwwww', '.lwwwww', '.lwlwww', '..lwwww', '..lwlww', '.oooooo', ...FOREHEAD, ...FACE],
    colors: { c: '#ece9fa', d: '#b7b2d8' },
  },
  blacksmith: {   // red bandana on a shaved head, soot on the cheek, leather apron
    rows: ['.......', '.......', '....ddd', '..ddrrr', '.drrrrr', '.dddddd', 'tssssss', 'tssssss',
      'jtsksss', 'jtsksss', '.tsssss', '.tseqss', '..tsssm', '...tsss', '..dcccc', '.dccccc'],
    colors: { c: '#6b4a32', d: '#3e2a1c', e: '#5a5470' },
  },
  miller: {       // floury beret
    rows: ['.......', '...llll', '.llwwww', 'lwwwwww', 'lwwwwww', '.oooooo', ...FOREHEAD, ...FACE],
    colors: { c: '#d8d2c0', d: '#a39c88' },
  },
  shepherd: {     // brown felt hat with a wide brim
    rows: ['.......', '...nnnn', '...nbbb', '..nbbbb', 'nnnnnnn', '.jhhhhh', ...FOREHEAD, ...FACE],
    colors: { c: '#8a9a5b', d: '#5b6b38' },
  },
  innkeeper: {    // hair in a high bun, waistcoat over a white shirt
    rows: ['.....jj', '....jhh', '.....jj', '..jjhhh', '.jhhhhh', '.jhhhhu', ...FOREHEAD,
      'jtsksss', 'jtsksss', '.tsssss', '.tsqsss', '..tsssm', '...tsss', '..dcwww', '.dccwww'],
    colors: { c: '#9e3a4a', d: '#5e1f2c' },
  },
  weaver: {       // patterned headscarf
    rows: ['.......', '...zzzz', '.zxxxxx', '.xxgxxg', 'zxxxxxx', 'zxxxxxx', 'xxjssss', 'xxtssss', ...FACE],
    colors: { x: '#2fb6b0', z: '#1d7a76', g: '#bff0ec', c: '#9466dc', d: '#5b3799' },
  },
  fisher: {       // yellow sou'wester, its brim down over the ears
    rows: ['.......', '....yyy', '..ayyyy', '.ayyyyy', 'aaaaaaa', 'ayjhhhh', 'yahjsss', 'a.tssss', ...FACE],
    colors: { c: '#2f5f8f', d: '#1c3a57' },
  },
  woodcutter: {   // red knitted cap with a pompom, and a beard
    rows: ['......r', '....rrr', '..rdrdr', '.rrrrrr', '.dddddd', '.jhhhhh', ...FOREHEAD, ...BEARD],
    colors: { c: '#3e5a7a', d: '#243a52' },
  },
  herbalist: {    // pointed green hood
    rows: ['......x', '.....xx', '....zxx', '...zxxx', '..zxxxx', '.zxxjhh', 'zxhjsss', 'zxtssss',
      'zxsksss', 'zxsksss', '.tsssss', '.tsqsss', '..tsssm', '...tsss', '..dcccc', '.dccccc'],
    colors: { x: '#3f8f5a', z: '#2a5f3c', c: '#7a5a3a', d: '#4e3824' },
  },
  potter: {       // terracotta headscarf, clay on the cheek
    rows: ['.......', '.......', '...zzzz', '..zxxxx', '.zxxxxx', '.jhhhhh', ...FOREHEAD,
      'jtsksss', 'jtsksss', '.tsssss', '.tszsss', '..tsssm', '...tsss', '..dcccc', '.dccccc'],
    colors: { x: '#d9703a', z: '#9a4520', c: '#b07a45', d: '#7a4a2a' },
  },
};
for (const trade of Object.values(TRADES)) trade.rows = outlined(mirror(trade.rows));

// The trade's portrait for a public role; apprentices wear their master's
// outfit in lighter colours. Unknown roles fall back to the name's face.
export function tradeAvatar(publicRole, name, scale = 3) {
  const apprentice = publicRole.endsWith('_apprentice');
  const trade = TRADES[apprentice ? publicRole.slice(0, -'_apprentice'.length) : publicRole];
  if (!trade) return avatar(name, scale);
  const n = hash(name || '?');
  const hair = HAIR[(n >>> 4) % HAIR.length];
  const skin = SKIN[(n >>> 8) % SKIN.length];
  const colors = { ...trade.colors };
  if (apprentice) {
    for (const key of Object.keys(colors)) colors[key] = mix(colors[key], '#ffffff', 0.35);
  }
  return draw(trade.rows, scale, {
    h: hair, j: mix(hair, COLORS.k, 0.45), u: mix(hair, '#ffffff', 0.35),
    s: skin, t: mix(skin, '#6b2f3a', 0.3), q: mix(skin, COLORS.r, 0.35), m: '#7a3b3b',
    ...colors,
  });
}

// ── Scenery ──────────────────────────────────────────────────────────────────

function seeded(seed) {
  let s = seed;
  return () => ((s = Math.imul(s ^ (s >>> 15), 2246822507) + 0x6d2b79f5 >>> 0) / 4294967296);
}

// The village along the bottom of the screen: far hills (F), houses, pines
// and the church (H), lit windows (L). Drawn at 2 CSS px per pixel.
export function skyline(width = 240, height = 40) {
  const rnd = seeded(11);
  const grid = Array.from({ length: height }, () => Array(width).fill('.'));
  const fill = (x, y, c) => { if (x >= 0 && x < width && y >= 0 && y < height) grid[y][x] = c; };
  for (let x = 0; x < width; x++) {
    const top = 12 + Math.round(4 * Math.sin(x / 23) + 2 * Math.sin(x / 7.3));
    for (let y = top; y < height; y++) fill(x, y, 'F');
    if ((x + top) % 2 === 0) fill(x, top - 1, 'F');
  }
  for (let x = 0; x < width; x++) {
    const top = height - 7 - Math.round(1.5 + 1.5 * Math.sin(x / 19));
    for (let y = top; y < height; y++) fill(x, y, 'H');
  }
  const pine = (x, base, h) => {
    for (let r = 0; r < h; r++) {
      const half = Math.floor((r % 4) + r / 3);
      for (let i = -half; i <= half; i++) fill(x + i, base - h + r, 'H');
    }
    fill(x, base, 'H');
    fill(x, base + 1, 'H');
  };
  const house = (x, w, wall, base) => {
    for (let y = base - wall; y < base; y++) for (let i = 0; i < w; i++) fill(x + i, y, 'H');
    const roof = Math.ceil(w / 2) + 1;
    for (let r = 1; r <= roof; r++) for (let i = r - 2; i <= w - r + 1; i++) fill(x + i, base - wall - r, 'H');
    for (let y = base - wall - roof + 1; y < base - wall - 2; y++) { fill(x + 2, y, 'H'); fill(x + 3, y, 'H'); }
    const wy = base - wall + 2;
    for (let dy = 0; dy < 3; dy++) {
      for (let dx = 0; dx < 2; dx++) {
        fill(x + 2 + dx, wy + dy, 'L');
        if (w > 9 && rnd() > 0.25) fill(x + w - 4 + dx, wy + dy, 'L');
      }
    }
  };
  const church = (x, base) => {
    house(x, 14, 9, base);
    const sx = x + 15;
    for (let y = base - 22; y < base; y++) for (let i = 0; i < 6; i++) fill(sx + i, y, 'H');
    for (let r = 0; r < 8; r++) for (let i = 0; i < 6; i++) if (Math.abs(i - 2.5) <= r / 2.6) fill(sx + i, base - 30 + r, 'H');
    for (let y = base - 35; y < base - 30; y++) { fill(sx + 2, y, 'H'); fill(sx + 3, y, 'H'); }
    for (let i = 1; i < 5; i++) fill(sx + i, base - 33, 'H');
    for (let dy = 0; dy < 4; dy++) { fill(sx + 2, base - 18 + dy, 'L'); fill(sx + 3, base - 18 + dy, 'L'); }
  };
  const base = height - 6;
  const mid = Math.floor(width / 2) - 10;
  for (let x = 3; x < width - 6;) {
    if (x > mid - 8 && x < mid + 8) { church(x, base); x += 26; continue; }
    if (rnd() < 0.4) { pine(x + 3, base, 9 + Math.floor(rnd() * 6)); x += 7 + Math.floor(rnd() * 3); continue; }
    const w = 9 + Math.floor(rnd() * 5);
    house(x, w, 6 + Math.floor(rnd() * 4), base);
    x += w + 4 + Math.floor(rnd() * 6);
  }
  const svg = draw(grid.map(r => r.join('')), 1);
  svg.removeAttribute('width');
  svg.removeAttribute('height');
  svg.setAttribute('preserveAspectRatio', 'xMidYMax slice');
  return svg;
}

// The sky: an ordered-dither gradient on a half-resolution canvas, with
// stars and a haloed moon at night, a sun and two clouds by day.
const BAYER = [[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]];
const rgb = hex => [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16));

export function paintSky(canvas, { colors, time }) {
  const W = Math.ceil(innerWidth / 2);
  const H = Math.ceil(innerHeight / 2);
  canvas.width = W;
  canvas.height = H;
  const ctx = canvas.getContext('2d');
  const img = ctx.createImageData(W, H);
  const stops = [[0, colors[0]], [0.45, colors[1]], [0.8, colors[2]], [1, colors[2]]];
  const cols = stops.map(([, c]) => rgb(c));
  for (let y = 0; y < H; y++) {
    const t = y / H;
    let i = 0;
    while (i < stops.length - 2 && t > stops[i + 1][0]) i++;
    const f = Math.min(1, Math.max(0, (t - stops[i][0]) / (stops[i + 1][0] - stops[i][0])));
    for (let x = 0; x < W; x++) {
      // Four flat steps per band, dithered where they meet.
      const q = f * 3;
      const step = Math.min(3, Math.floor(q) + ((q % 1) * 16 > BAYER[y % 4][x % 4] ? 1 : 0)) / 3;
      const a = cols[i];
      const b = cols[i + 1];
      const o = (y * W + x) * 4;
      for (let ch = 0; ch < 3; ch++) img.data[o + ch] = a[ch] + (b[ch] - a[ch]) * step;
      img.data[o + 3] = 255;
    }
  }
  ctx.putImageData(img, 0, 0);
  const rnd = seeded(5);
  const dot = (x, y, color) => { ctx.fillStyle = color; ctx.fillRect(x, y, 1, 1); };
  const cx = Math.round(W * 0.8);
  const cy = 62;
  if (time !== 'day') {
    for (let s = 0; s < 70; s++) {
      const x = Math.floor(rnd() * W);
      const y = Math.floor(rnd() * H * 0.62);
      const color = rnd() > 0.7 ? '#f4f1ff' : 'rgba(244,241,255,0.55)';
      dot(x, y, color);
      if (s % 11 === 0) { ctx.fillRect(x - 1, y, 3, 1); ctx.fillRect(x, y - 1, 1, 3); }
    }
  }
  if (time === 'night') {
    for (let y = -26; y <= 26; y++) {
      for (let x = -26; x <= 26; x++) {
        const d = Math.hypot(x, y);
        if (d > 13 && d < 26 && (x + y) % 2 === 0 && (d < 19 || (x % 2 === 0 && y % 2 === 0))) {
          dot(cx + x, cy + y, 'rgba(244,241,255,0.12)');
        }
      }
    }
    for (let y = -13; y <= 13; y++) {
      for (let x = -13; x <= 13; x++) {
        const d = Math.hypot(x, y);
        if (d > 13) continue;
        const crater = Math.hypot(x + 4, y - 3) < 3 || Math.hypot(x - 5, y + 5) < 2 || Math.hypot(x - 3, y - 6) < 1.6;
        dot(cx + x, cy + y, d > 11.5 || x + y > 12 ? '#cfc6a0' : crater ? '#e4dcb6' : '#fbf6dc');
      }
    }
  } else if (time === 'day') {
    for (let y = -12; y <= 12; y++) {
      for (let x = -12; x <= 12; x++) {
        const d = Math.hypot(x, y);
        if (d <= 9) dot(cx + x, cy + y, d > 7.5 ? '#ffc94a' : '#fff1a8');
        else if (d < 12 && (x + y) % 2 === 0) dot(cx + x, cy + y, 'rgba(255,241,168,0.45)');
      }
    }
    for (const [x0, y0, w] of [[Math.round(W * 0.08), 150, 34], [Math.round(W * 0.5), 205, 26]]) {
      ctx.fillStyle = '#ffffff';
      ctx.fillRect(x0, y0, w, 4);
      ctx.fillRect(x0 + 5, y0 - 3, w - 14, 3);
      ctx.fillRect(x0 + 10, y0 - 6, 8, 3);
      ctx.fillStyle = '#d7ecff';
      ctx.fillRect(x0 + 2, y0 + 4, w - 4, 1);
    }
  }
}
