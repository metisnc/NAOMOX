// Catalogue : libellés, couleurs, filtres, tris et regroupements des jeux.

import type { Game } from './types';

// --------------------------------------------------------------------------- libellés

export const SYSTEMS: Record<string, { short: string; color: string }> = {
  'Sega Naomi': { short: 'Naomi', color: '#f2a33a' },
  'Sega Naomi2': { short: 'Naomi 2', color: '#e5534b' },
  'Sammy Atomiswave': { short: 'Atomiswave', color: '#3fa7e0' },
  'Sega Chihiro': { short: 'Chihiro', color: '#36c27e' },
  'Sega Triforce': { short: 'Triforce', color: '#a77bea' },
};
export const systemShort = (s: string) => SYSTEMS[s]?.short ?? s;
export const systemColor = (s: string) => SYSTEMS[s]?.color ?? '#9aa5b1';

const GENRES: Record<string, string> = {
  Fighter: 'Combat',
  Driving: 'Course',
  Sports: 'Sport',
  Shooter: 'Shoot’em up',
  Puzzle: 'Puzzle',
  Gun: 'Tir au pistolet',
  "Beat-'Em-Up": 'Beat’em up',
  Rhythm: 'Rythme',
  Quiz: 'Quiz',
  Action: 'Action',
  Flying: 'Vol',
  Miscellaneous: 'Divers',
  Platform: 'Plates-formes',
  Casino: 'Casino',
  Adventure: 'Aventure',
  Mahjong: 'Mahjong',
};
export const genreLabel = (g: string) => (g ? (GENRES[g] ?? g) : 'Non classé');

const GENRE_ICONS: Record<string, string> = {
  Fighter: '🥊', Driving: '🏁', Sports: '⚽', Shooter: '🚀', Puzzle: '🧩', Gun: '🎯',
  "Beat-'Em-Up": '👊', Rhythm: '🥁', Quiz: '❓', Action: '⚡', Flying: '✈️', Miscellaneous: '🎲',
  Platform: '🍄', Casino: '🎰', Adventure: '🗺️', Mahjong: '🀄',
};
export const genreIcon = (g: string) => GENRE_ICONS[g] ?? '🕹️';

const CONTROLS: Record<string, string> = {
  'Digital (Stick)': 'Joystick',
  'Analog (Stick)': 'Stick analogique',
  'Analog (Driving)': 'Volant',
  'Analog (Trackball)': 'Trackball',
  'Digital (Keyboard)': 'Clavier',
  Lightgun: 'Pistolet',
  Other: 'Spécifique',
};
export const controlsLabel = (c: string) => (c ? (CONTROLS[c] ?? c) : '—');

export const orientationLabel = (o: string) => (o === 'Vertical' ? 'Vertical (TATE)' : o === 'Horizontal' ? 'Horizontal' : o || '—');

export function ratingInfo(r: string): { label: string; color: string } | null {
  if (!r) return null;
  if (r.includes('Green')) return { label: 'Tous publics', color: '#36c27e' };
  if (r.includes('Yellow')) return { label: 'Violence légère', color: '#e7b416' };
  if (r.includes('Red')) return { label: 'Violence', color: '#e5534b' };
  return { label: 'Non classé', color: '#9aa5b1' };
}

/** « Sammy/SNK Playmore » → « Sammy », « Moss (Taito license) » → « Moss ». */
export function publisher(m: string): string {
  const first = (m || '').split(/[/(]/)[0].trim();
  if (!first) return 'Inconnu';
  const k = first.toLowerCase().replace(/[^a-z0-9]/g, '');
  const canon: Record<string, string> = { grev: 'G.Rev', arcsystemworks: 'Arc System Works', ecolesoftware: 'Ecole', ecole: 'Ecole' };
  return canon[k] ?? first;
}

// --------------------------------------------------------------------------- recherche

export const fold = (s: string) =>
  (s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();

function haystack(g: Game): string {
  return fold([g.name, g.rom, g.manufacturer, g.genre, genreLabel(g.genre), g.year, g.game_id, systemShort(g.system)].join(' '));
}

// --------------------------------------------------------------------------- filtres

export interface Filters {
  systems: string[];
  genres: string[];
  controls: string[];
  publishers: string[];
  orientation: '' | 'Horizontal' | 'Vertical';
  ratings: string[];
  yearMin: number | null;
  yearMax: number | null;
  cabinet: string | null; // id de borne : seulement les jeux compatibles
  favOnly: boolean;
  playedOnly: boolean;
  installedOnly: boolean;
  showDisabled: boolean;
}

export const emptyFilters = (): Filters => ({
  systems: [],
  genres: [],
  controls: [],
  publishers: [],
  orientation: '',
  ratings: [],
  yearMin: null,
  yearMax: null,
  cabinet: null,
  favOnly: false,
  playedOnly: false,
  installedOnly: true,
  showDisabled: false,
});

/** Nombre de critères « actifs » (hors réglages d'affichage par défaut). */
export function activeCount(f: Filters): number {
  return (
    f.systems.length + f.genres.length + f.controls.length + f.publishers.length + f.ratings.length +
    (f.orientation ? 1 : 0) + (f.yearMin !== null || f.yearMax !== null ? 1 : 0) + (f.cabinet ? 1 : 0) +
    (f.favOnly ? 1 : 0) + (f.playedOnly ? 1 : 0) + (f.installedOnly ? 0 : 1) + (f.showDisabled ? 1 : 0)
  );
}

export function ratingKey(r: string): string {
  return ratingInfo(r)?.label ?? 'Non classé';
}

export function applyFilters(
  games: Game[],
  f: Filters,
  query: string,
  compatibleSystems: string[] | null,
): Game[] {
  const words = fold(query).split(/\s+/).filter(Boolean);
  return games.filter((g) => {
    if (!f.showDisabled && !g.enabled) return false;
    if (f.installedOnly && !g.present) return false;
    if (f.favOnly && !g.favourite) return false;
    if (f.playedOnly && !g.plays) return false;
    if (f.systems.length && !f.systems.includes(g.system)) return false;
    if (f.genres.length && !f.genres.includes(g.genre)) return false;
    if (f.controls.length && !f.controls.includes(g.controls)) return false;
    if (f.publishers.length && !f.publishers.includes(publisher(g.manufacturer))) return false;
    if (f.ratings.length && !f.ratings.includes(ratingKey(g.rating))) return false;
    if (f.orientation && g.orientation !== f.orientation) return false;
    const y = Number(g.year) || null;
    if (f.yearMin !== null && (y === null || y < f.yearMin)) return false;
    if (f.yearMax !== null && (y === null || y > f.yearMax)) return false;
    if (compatibleSystems && !compatibleSystems.includes(g.system)) return false;
    if (words.length) {
      const h = haystack(g);
      if (!words.every((w) => h.includes(w))) return false;
    }
    return true;
  });
}

/** Valeurs disponibles (avec effectif) pour un critère, calculées sur le catalogue courant. */
export function facet(games: Game[], key: (g: Game) => string): { value: string; count: number }[] {
  const m = new Map<string, number>();
  for (const g of games) {
    const v = key(g);
    if (v) m.set(v, (m.get(v) ?? 0) + 1);
  }
  return [...m.entries()].map(([value, count]) => ({ value, count })).sort((a, b) => b.count - a.count || a.value.localeCompare(b.value));
}

// --------------------------------------------------------------------------- tri et groupes

export type SortKey = 'name' | 'name-desc' | 'year-desc' | 'year' | 'publisher' | 'system' | 'genre' | 'plays' | 'recent';

export const SORTS: { key: SortKey; label: string }[] = [
  { key: 'name', label: 'Nom (A → Z)' },
  { key: 'name-desc', label: 'Nom (Z → A)' },
  { key: 'year-desc', label: 'Année (récents)' },
  { key: 'year', label: 'Année (anciens)' },
  { key: 'genre', label: 'Genre' },
  { key: 'system', label: 'Système' },
  { key: 'publisher', label: 'Éditeur' },
  { key: 'plays', label: 'Les plus joués' },
  { key: 'recent', label: 'Joués récemment' },
];

const byName = (a: Game, b: Game) => a.name.localeCompare(b.name, 'fr', { sensitivity: 'base' });
const SYSTEM_ORDER = Object.keys(SYSTEMS);

export function sortGames(games: Game[], key: SortKey, favFirst: boolean): Game[] {
  const year = (g: Game) => Number(g.year) || 0;
  const cmp: Record<SortKey, (a: Game, b: Game) => number> = {
    name: byName,
    'name-desc': (a, b) => byName(b, a),
    'year-desc': (a, b) => year(b) - year(a) || byName(a, b),
    year: (a, b) => (year(a) || 9999) - (year(b) || 9999) || byName(a, b),
    publisher: (a, b) => publisher(a.manufacturer).localeCompare(publisher(b.manufacturer)) || byName(a, b),
    system: (a, b) => SYSTEM_ORDER.indexOf(a.system) - SYSTEM_ORDER.indexOf(b.system) || byName(a, b),
    genre: (a, b) => genreLabel(a.genre).localeCompare(genreLabel(b.genre)) || byName(a, b),
    plays: (a, b) => b.plays - a.plays || (b.last_played ?? 0) - (a.last_played ?? 0) || byName(a, b),
    recent: (a, b) => (b.last_played ?? 0) - (a.last_played ?? 0) || byName(a, b),
  };
  const sorted = [...games].sort(cmp[key]);
  return favFirst ? [...sorted.filter((g) => g.favourite), ...sorted.filter((g) => !g.favourite)] : sorted;
}

export interface Group {
  key: string;
  label: string;
  games: Game[];
}

/** Regroupe selon le tri (lettre, année, genre, système, éditeur). */
export function groupGames(sorted: Game[], key: SortKey): Group[] {
  const label = (g: Game): string => {
    switch (key) {
      case 'name':
      case 'name-desc': {
        const c = fold(g.name).charAt(0).toUpperCase();
        return /[A-Z]/.test(c) ? c : '#';
      }
      case 'year':
      case 'year-desc':
        return g.year || 'Année inconnue';
      case 'genre':
        return `${genreIcon(g.genre)} ${genreLabel(g.genre)}`;
      case 'system':
        return systemShort(g.system);
      case 'publisher':
        return publisher(g.manufacturer);
      case 'plays':
        return g.plays ? (g.plays >= 10 ? '10 parties et plus' : g.plays >= 3 ? '3 à 9 parties' : '1 ou 2 parties') : 'Jamais joués';
      case 'recent':
        return recencyBucket(g.last_played);
    }
  };
  const groups: Group[] = [];
  for (const g of sorted) {
    const l = label(g);
    const last = groups[groups.length - 1];
    if (last && last.label === l) last.games.push(g);
    else groups.push({ key: `${groups.length}-${l}`, label: l, games: [g] });
  }
  return groups;
}

function recencyBucket(ts: number | null): string {
  if (!ts) return 'Jamais joués';
  const days = (Date.now() / 1000 - ts) / 86400;
  if (days < 1) return 'Aujourd’hui';
  if (days < 7) return 'Cette semaine';
  if (days < 31) return 'Ce mois-ci';
  return 'Plus ancien';
}

export function sameGenre(all: Game[], g: Game, n = 12): Game[] {
  return all
    .filter((x) => x.rom !== g.rom && x.present && x.enabled && x.genre === g.genre)
    .sort((a, b) => Number(a.system !== g.system) - Number(b.system !== g.system) || b.plays - a.plays || byName(a, b))
    .slice(0, n);
}

// Variantes d'un même jeu (débloqué, révision, région…) : lues dans le nom affiché ou dans le
// nom de fichier, et retirées du titre pour qu'elles restent visibles sous forme de badges.
const NAME_TAGS: [RegExp, (m: RegExpMatchArray) => string][] = [
  [/\s*\bunlocked\b/i, () => 'Débloqué'],
  [/\s*\bdebug\b/i, () => 'Debug'],
  [/\s*\b(?:rev|ver)\.?\s*([a-z]\d?)\b/i, (m) => `Rév. ${m[1].toUpperCase()}`],
  [/\s*\(export\)/i, () => 'Export'],
  [/\s*\(japan\)/i, () => 'Japon'],
  [/\s*\(usa\)/i, () => 'USA'],
  [/\s*\bcycraft\b/i, () => 'Cycraft'],
  [/\s*\bno comms? board\b/i, () => 'Sans carte comm.'],
];
const ROM_TAGS: [RegExp, (m: RegExpMatchArray) => string][] = [
  [/unlocked/, () => 'Débloqué'],
  [/debug/, () => 'Debug'],
  // « _rev.b-[…] », « _rev_a-[…] », « _ver.b-[…] » — mais pas « revenge ».
  [/[_.-](?:rev|ver)[._]([a-z]\d?)(?=[-_.\]]|$)/, (m) => `Rév. ${m[1].toUpperCase()}`],
  [/_export\b|export_/, () => 'Export'],
  [/_japan\b|japan_/, () => 'Japon'],
  [/_usa\b/, () => 'USA'],
  [/cycraft/, () => 'Cycraft'],
  [/no_comm_board/, () => 'Sans carte comm.'],
];

const parsed = new Map<string, { name: string; tags: string[] }>();

function parse(g: Game): { name: string; tags: string[] } {
  const key = `${g.rom}\u0000${g.name}`;
  const hit = parsed.get(key);
  if (hit) return hit;
  let name = g.name;
  const tags: string[] = [];
  for (const [re, label] of NAME_TAGS) {
    const m = name.match(re);
    if (m) {
      tags.push(label(m));
      name = name.replace(re, '');
    }
  }
  const r = g.rom.toLowerCase().replace(/\.bin(\.gz)?$/, '');
  for (const [re, label] of ROM_TAGS) {
    const m = r.match(re);
    if (m && !tags.includes(label(m))) tags.push(label(m));
  }
  const res = { name: name.replace(/\s{2,}/g, ' ').replace(/[\s,–-]+$/, '').trim() || g.name, tags };
  parsed.set(key, res);
  return res;
}

/** Badges de variante. */
export const variants = (g: Game): string[] => parse(g).tags;
/** Nom sans les mentions de variante. */
export const displayName = (g: Game): string => parse(g).name;
