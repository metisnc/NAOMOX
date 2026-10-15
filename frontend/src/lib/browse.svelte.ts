// Préférences de navigation dans le catalogue (tri, filtres, vue), mémorisées localement.

import { emptyFilters, type Filters, type SortKey } from './catalog';

export type View = 'auto' | 'grid' | 'list';
export type Density = 'S' | 'M' | 'L';

interface Saved {
  filters: Filters;
  sort: SortKey;
  favFirst: boolean;
  view: View;
  density: Density;
}

const KEY = 'naomox.browse.v1';

function load(): Saved {
  const d: Saved = { filters: emptyFilters(), sort: 'name', favFirst: false, view: 'auto', density: 'M' };
  try {
    const raw = JSON.parse(localStorage.getItem(KEY) ?? '{}');
    return { ...d, ...raw, filters: { ...d.filters, ...(raw.filters ?? {}) } };
  } catch {
    return d;
  }
}

class Browse {
  #s = load();
  filters = $state<Filters>(this.#s.filters);
  sort = $state<SortKey>(this.#s.sort);
  favFirst = $state(this.#s.favFirst);
  view = $state<View>(this.#s.view);
  density = $state<Density>(this.#s.density);
  query = $state('');

  save(): void {
    try {
      localStorage.setItem(
        KEY,
        JSON.stringify({ filters: this.filters, sort: this.sort, favFirst: this.favFirst, view: this.view, density: this.density }),
      );
    } catch {
      /* stockage indisponible */
    }
  }

  reset(): void {
    this.filters = emptyFilters();
    this.query = '';
  }

  toggle<K extends 'systems' | 'genres' | 'controls' | 'publishers' | 'ratings'>(key: K, value: string): void {
    const list = this.filters[key];
    this.filters[key] = list.includes(value) ? list.filter((v) => v !== value) : [...list, value];
  }
}

export const browse = new Browse();
