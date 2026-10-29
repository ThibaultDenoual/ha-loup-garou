import { ref } from './i18n.js';

// Display order for setup and the rules reference.
export const ROLE_ORDER = [
  'villager', 'werewolf', 'seer', 'hunter', 'elder', 'scapegoat',
  'little_girl', 'witch', 'cupid', 'alpha_wolf', 'minion', 'sheriff',
];

// Mirrors BaseRole.team in roles/impl/.
const WOLVES = new Set(['werewolf', 'alpha_wolf', 'minion']);
export const teamOf = roleId => (WOLVES.has(roleId) ? 'wolves' : 'village');

// Wolves never target their own pack.
const PACK = new Set(['werewolf', 'alpha_wolf']);
export const isPack = roleId => PACK.has(roleId);

// Grammatical gender for the {article} placeholder in narration lines.
const FEMININE = new Set(['seer', 'witch', 'little_girl']);
export const articleRef = roleId => ref(FEMININE.has(roleId) ? 'article.female' : 'article.male');

export const roleNameRef = roleId => ref(`role.${roleId}.name`);
