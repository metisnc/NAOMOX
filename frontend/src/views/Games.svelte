<script lang="ts">
  import GameTile from '../components/GameTile.svelte';
  import Marquee from '../components/Marquee.svelte';
  import Shelf from '../components/Shelf.svelte';
  import { browse, type View } from '../lib/browse.svelte';
  import {
    SORTS,
    SYSTEMS,
    activeCount,
    applyFilters,
    controlsLabel,
    facet,
    genreIcon,
    genreLabel,
    groupGames,
    sortGames,
    systemColor,
    systemShort,
    variants,
    displayName,
  } from '../lib/catalog';
  import { app } from '../lib/state.svelte';
  import type { Game } from '../lib/types';
  import FilterPanel from './FilterPanel.svelte';
  import GameSheet from './GameSheet.svelte';

  let selected = $state<string | null>(null);
  let sheetOpen = $state(false);
  let filtersOpen = $state(false);

  // Jeux en cours d'exécution : rom → noms des bornes.
  const playing = $derived.by(() => {
    const m = new Map<string, string[]>();
    for (const c of app.cabinets) {
      const rom = c.status.current_job?.kind === 'launch' ? null : c.status.game;
      if (rom) m.set(rom, [...(m.get(rom) ?? []), c.name]);
    }
    return m;
  });

  const compatSystems = $derived.by(() => {
    const cab = app.cabinets.find((c) => c.id === browse.filters.cabinet);
    return cab ? (app.systems?.compatibility[cab.type] ?? []) : null;
  });

  const filtered = $derived(applyFilters(app.games, browse.filters, browse.query, compatSystems));
  const sorted = $derived(sortGames(filtered, browse.sort, browse.favFirst));
  const groups = $derived(groupGames(sorted, browse.sort));
  const nActive = $derived(activeCount(browse.filters));

  // Vue « rayons » quand on ne cherche ni ne filtre.
  const showShelves = $derived(browse.view === 'auto' && !browse.query.trim() && nActive === 0);

  const launchable = $derived(app.games.filter((g) => g.present && g.enabled));
  const recent = $derived(
    launchable.filter((g) => g.last_played).sort((a, b) => (b.last_played ?? 0) - (a.last_played ?? 0)).slice(0, 12),
  );
  const favourites = $derived(launchable.filter((g) => g.favourite).sort((a, b) => a.name.localeCompare(b.name)));
  const mostPlayed = $derived(launchable.filter((g) => g.plays > 1).sort((a, b) => b.plays - a.plays).slice(0, 12));
  const genreShelves = $derived(
    facet(launchable, (g) => g.genre).map((f) => ({
      genre: f.value,
      games: sortGames(launchable.filter((g) => g.genre === f.value), 'plays', true).slice(0, 16),
      count: f.count,
    })),
  );
  const featured = $derived<Game | undefined>(recent[0] ?? favourites[0] ?? launchable.find((g) => g.video));

  const pills = $derived.by(() => {
    const f = browse.filters;
    const out: { label: string; color?: string; clear: () => void }[] = [];
    for (const s of f.systems) out.push({ label: systemShort(s), color: systemColor(s), clear: () => browse.toggle('systems', s) });
    for (const g of f.genres) out.push({ label: `${genreIcon(g)} ${genreLabel(g)}`, clear: () => browse.toggle('genres', g) });
    for (const c of f.controls) out.push({ label: controlsLabel(c), clear: () => browse.toggle('controls', c) });
    for (const p of f.publishers) out.push({ label: p, clear: () => browse.toggle('publishers', p) });
    for (const r of f.ratings) out.push({ label: r, clear: () => browse.toggle('ratings', r) });
    if (f.orientation) out.push({ label: f.orientation === 'Vertical' ? '▯ Vertical' : '▭ Horizontal', clear: () => (f.orientation = '') });
    if (f.yearMin !== null || f.yearMax !== null)
      out.push({ label: `${f.yearMin ?? '…'} – ${f.yearMax ?? '…'}`, clear: () => ((f.yearMin = null), (f.yearMax = null)) });
    if (f.cabinet) {
      const cab = app.cabinets.find((c) => c.id === f.cabinet);
      out.push({ label: `🕹️ ${cab?.name ?? 'borne'}`, clear: () => (f.cabinet = null) });
    }
    if (f.favOnly) out.push({ label: '★ Favoris', clear: () => (f.favOnly = false) });
    if (f.playedOnly) out.push({ label: 'Déjà lancés', clear: () => (f.playedOnly = false) });
    if (!f.installedOnly) out.push({ label: 'Avec jeux sans ROM', clear: () => (f.installedOnly = true) });
    if (f.showDisabled) out.push({ label: 'Avec désactivés', clear: () => (f.showDisabled = false) });
    return out;
  });

  $effect(() => {
    void JSON.stringify(browse.filters);
    void browse.view;
    void browse.density;
    void browse.sort;
    browse.save();
  });

  function open(g: Game) {
    selected = g.rom;
    sheetOpen = true;
  }

  function surprise() {
    const pool = filtered.filter((g) => g.present && g.enabled);
    if (pool.length) open(pool[Math.floor(Math.random() * pool.length)]);
  }

  function showGenre(genre: string) {
    browse.filters.genres = [genre];
    browse.view = browse.view === 'auto' ? 'auto' : browse.view;
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  function setView(v: View) {
    browse.view = v;
  }

  const installed = $derived(app.games.filter((g) => g.present).length);
</script>

<div class="page">
  <div class="toolbar">
    <div class="search">
      <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" /></svg>
      <input type="search" placeholder="Jeu, éditeur, genre, année…" bind:value={browse.query} aria-label="Rechercher" />
      {#if browse.query}<button class="ghost clear" onclick={() => (browse.query = '')} aria-label="Effacer">✕</button>{/if}
    </div>
    <button class="filters" class:has={nActive > 0} onclick={() => (filtersOpen = true)} aria-label="Trier et filtrer">
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 6h16M7 12h10M10 18h4" /></svg>
      {#if nActive}<b>{nActive}</b>{/if}
    </button>
  </div>

  <div class="quick">
    {#each Object.keys(SYSTEMS) as s (s)}
      {#if app.games.some((g) => g.system === s && g.present)}
        <button class="chip sys" style="--c:{systemColor(s)}" class:on={browse.filters.systems.includes(s)} onclick={() => browse.toggle('systems', s)}>
          <i></i>{systemShort(s)}
        </button>
      {/if}
    {/each}
    <button class="chip" class:on={browse.filters.favOnly} onclick={() => (browse.filters.favOnly = !browse.filters.favOnly)}>★ Favoris</button>
  </div>

  {#if pills.length}
    <div class="pills">
      {#each pills as p (p.label)}
        <button class="pill" style={p.color ? `--c:${p.color}` : ''} onclick={p.clear}>{p.label} <span>✕</span></button>
      {/each}
      <button class="ghost small" onclick={() => browse.reset()}>Tout effacer</button>
    </div>
  {/if}

  <div class="bar">
    <span class="muted small count" title={installed < app.games.length && browse.filters.installedOnly ? `${app.games.length - installed} jeux sans ROM masqués` : ''}>{filtered.length} jeu{filtered.length > 1 ? 'x' : ''}</span>
    <span class="grow"></span>
    <select class="sort" bind:value={browse.sort} aria-label="Tri">
      {#each SORTS as s (s.key)}<option value={s.key}>{s.label}</option>{/each}
    </select>
    <div class="seg" role="group" aria-label="Affichage">
      <button class:on={browse.view === 'auto'} onclick={() => setView('auto')} title="Rayons" aria-label="Rayons">
        <svg viewBox="0 0 24 24"><path d="M3 6h18M3 12h18M3 18h18" /></svg>
      </button>
      <button class:on={browse.view === 'grid'} onclick={() => setView('grid')} title="Grille" aria-label="Grille">
        <svg viewBox="0 0 24 24"><path d="M4 4h7v7H4zM13 4h7v7h-7zM4 13h7v7H4zM13 13h7v7h-7z" /></svg>
      </button>
      <button class:on={browse.view === 'list'} onclick={() => setView('list')} title="Liste" aria-label="Liste">
        <svg viewBox="0 0 24 24"><path d="M9 6h11M9 12h11M9 18h11M4 6h1M4 12h1M4 18h1" /></svg>
      </button>
    </div>
    {#if browse.view !== 'list'}
      <button class="small ghost density" onclick={() => (browse.density = browse.density === 'S' ? 'M' : browse.density === 'M' ? 'L' : 'S')} title="Taille des vignettes">
        {browse.density}
      </button>
    {/if}
  </div>

  {#if !app.games.length}
    <p class="empty">Aucun jeu.</p>
  {:else if !installed && browse.filters.installedOnly}
    <div class="empty">
      <p>Aucune ROM installée sur le serveur.</p>
      <p class="small">Copiez les fichiers <code>.bin.gz</code> dans <code>/srv/naomox/roms</code> ou utilisez <a href="#/reglages">Réglages → Fichiers</a>.</p>
    </div>
  {:else if showShelves}
    {#if featured}
      <button class="hero" style="--sys:{systemColor(featured.system)}" onclick={() => featured && open(featured)}>
        {#if featured.video}
          <video src={featured.video} muted autoplay loop playsinline preload="metadata"></video>
        {/if}
        <div class="hero-shade"></div>
        <div class="hero-content">
          <span class="kicker">{recent[0] === featured ? 'Reprendre' : favourites[0] === featured ? 'Favori' : 'À découvrir'}</span>
          <div class="hero-logo"><Marquee image={featured.image} name={featured.name} system={featured.system} size="lg" /></div>
          <span class="hero-meta">{systemShort(featured.system)} · {featured.year} · {genreLabel(featured.genre)}</span>
        </div>
      </button>
    {/if}
    <div class="actions">
      <button onclick={surprise}>🎲 Au hasard</button>
      <button onclick={() => setView('grid')}>Tous les jeux ({filtered.length})</button>
    </div>
    <Shelf title="Joués récemment" games={recent} {playing} onopen={open} onmore={() => { browse.sort = 'recent'; setView('grid'); }} />
    <Shelf title="★ Favoris" games={favourites} {playing} onopen={open} onmore={() => (browse.filters.favOnly = true)} />
    <Shelf title="Les plus joués" games={mostPlayed} {playing} onopen={open} onmore={() => { browse.sort = 'plays'; setView('grid'); }} />
    {#each genreShelves as s (s.genre)}
      <Shelf title={`${genreIcon(s.genre)} ${genreLabel(s.genre)} · ${s.count}`} games={s.games} {playing} onopen={open} onmore={() => showGenre(s.genre)} />
    {/each}
  {:else if !sorted.length}
    <div class="empty">
      <p>Aucun jeu ne correspond.</p>
      <button onclick={() => browse.reset()}>Effacer la recherche et les filtres</button>
    </div>
  {:else}
    {#each groups as grp (grp.key)}
      <section class="group">
        {#if groups.length > 1}<h3 class="ghead">{grp.label} <small>{grp.games.length}</small></h3>{/if}
        {#if browse.view === 'list'}
          <ul class="list">
            {#each grp.games as g (g.rom)}
              <li>
                <button class="lrow" class:off={!g.present || !g.enabled} onclick={() => open(g)} style="--sys:{systemColor(g.system)}">
                  <span class="lm"><Marquee image={g.image} name={g.name} system={g.system} size="sm" /></span>
                  <span class="lt">
                    <strong>{g.favourite ? '★ ' : ''}{displayName(g)}{variants(g).length ? ` · ${variants(g).join(', ')}` : ''}</strong>
                    <span class="muted small"><i class="sd"></i>{systemShort(g.system)} · {g.year || '—'} · {genreLabel(g.genre)}{g.plays ? ` · ${g.plays}×` : ''}</span>
                  </span>
                  {#if playing.get(g.rom)}<span class="badge live">● {playing.get(g.rom)?.[0]}</span>{/if}
                </button>
              </li>
            {/each}
          </ul>
        {:else}
          <div class="grid d{browse.density}">
            {#each grp.games as g (g.rom)}
              <GameTile game={g} playingOn={playing.get(g.rom)} onopen={open} compact={browse.density === 'S'} />
            {/each}
          </div>
        {/if}
      </section>
    {/each}
  {/if}
</div>

<FilterPanel bind:open={filtersOpen} resultCount={filtered.length} />
{#if selected}
  <GameSheet bind:open={sheetOpen} bind:rom={selected} />
{/if}

<style>
  .toolbar { position: sticky; top: 52px; z-index: 6; display: flex; gap: 0.5rem; padding: 0.5rem 0; background: var(--bg); }
  .search { position: relative; flex: 1; }
  .search svg { position: absolute; left: 12px; top: 50%; translate: 0 -50%; width: 18px; height: 18px; fill: none; stroke: var(--fg-2); stroke-width: 2; }
  .search input { padding-left: 2.4rem; border-radius: 12px; background: var(--bg-2); }
  .clear { position: absolute; right: 2px; top: 2px; min-height: 40px; }
  .filters { position: relative; width: 48px; padding: 0; border-radius: 12px; }
  .filters svg { width: 22px; height: 22px; fill: none; stroke: currentColor; stroke-width: 2; stroke-linecap: round; }
  .filters.has { border-color: var(--accent); color: var(--accent); }
  .filters b { position: absolute; top: -6px; right: -6px; min-width: 20px; height: 20px; border-radius: 99px; background: var(--accent); color: var(--accent-fg); font-size: 0.72rem; display: grid; place-items: center; }

  .quick, .pills { display: flex; gap: 0.4rem; overflow-x: auto; scrollbar-width: none; padding: 0.15rem 0; }
  .pills { flex-wrap: wrap; overflow: visible; margin-top: 0.3rem; }
  .chip { min-height: 34px; padding: 0.2rem 0.75rem; border-radius: 99px; white-space: nowrap; font-size: 0.88rem; }
  .chip.on { background: var(--accent); color: var(--accent-fg); border-color: transparent; }
  .chip.sys i { width: 9px; height: 9px; border-radius: 50%; background: var(--c); box-shadow: 0 0 6px var(--c); }
  .chip.sys.on { background: var(--c); color: #111; }
  .chip.sys.on i { background: #111; box-shadow: none; }
  .pill { min-height: 30px; padding: 0.1rem 0.6rem; border-radius: 99px; font-size: 0.82rem; border-color: var(--c, var(--accent)); color: var(--fg); background: color-mix(in srgb, var(--c, var(--accent)) 18%, transparent); }
  .pill span { opacity: 0.6; font-size: 0.7rem; }

  .bar { display: flex; align-items: center; gap: 0.4rem; margin: 0.6rem 0 0.4rem; }
  .count { white-space: nowrap; }
  .sort { width: auto; min-width: 0; max-width: 46vw; min-height: 36px; padding: 0.2rem 0.5rem; font-size: 0.85rem; background: var(--bg-2); }
  .seg { display: inline-flex; border: 1px solid var(--line); border-radius: 10px; overflow: hidden; }
  .seg button { border: 0; border-radius: 0; min-height: 36px; width: 38px; padding: 0; background: transparent; }
  .seg button.on { background: var(--bg-3); color: var(--accent); }
  .seg svg { width: 18px; height: 18px; fill: none; stroke: currentColor; stroke-width: 2; stroke-linecap: round; }
  .density { width: 36px; min-height: 36px; padding: 0; font-weight: 800; }

  .hero {
    position: relative; display: block; width: 100%; padding: 0; overflow: hidden; border-radius: 18px;
    aspect-ratio: 16 / 9; max-height: 340px; border: 1px solid color-mix(in srgb, var(--sys) 45%, var(--line));
    background: radial-gradient(120% 120% at 50% 0%, color-mix(in srgb, var(--sys) 40%, #000), #05070a);
    margin: 0.4rem 0 0.8rem;
  }
  .hero video { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; opacity: 0.55; }
  .hero-shade { position: absolute; inset: 0; background: linear-gradient(180deg, rgb(0 0 0 / 0.1), rgb(0 0 0 / 0.75)); }
  .hero-content { position: absolute; inset: 0; display: grid; grid-template-rows: auto 1fr auto; justify-items: center; padding: 0.8rem 1rem 1rem; gap: 0.3rem; }
  .kicker { justify-self: start; font-size: 0.72rem; font-weight: 800; letter-spacing: 0.12em; text-transform: uppercase; color: #fff; background: var(--sys); padding: 0.15rem 0.55rem; border-radius: 99px; color: #111; }
  .hero-logo { align-self: center; width: min(78%, 420px); }
  .hero-meta { color: #e8ecf1; font-size: 0.85rem; text-shadow: 0 1px 3px #000; }
  .actions { display: flex; gap: 0.5rem; margin-bottom: 0.4rem; }
  .actions button { flex: 1; min-height: 40px; font-size: 0.9rem; }

  .group { margin-bottom: 0.6rem; }
  .ghead { position: sticky; top: 112px; z-index: 4; margin: 0.6rem 0 0.5rem; padding: 0.35rem 0; background: var(--bg); font-size: 1rem; }
  .ghead small { color: var(--fg-2); font-weight: 500; font-size: 0.8rem; margin-left: 0.3rem; }
  .grid { display: grid; gap: 0.7rem; }
  .grid.dS { grid-template-columns: repeat(auto-fill, minmax(110px, 1fr)); gap: 0.5rem; }
  .grid.dM { grid-template-columns: repeat(auto-fill, minmax(158px, 1fr)); }
  .grid.dL { grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); }

  .list { list-style: none; margin: 0; padding: 0; display: grid; gap: 0.4rem; }
  .lrow { width: 100%; justify-content: flex-start; gap: 0.75rem; padding: 0.35rem 0.6rem 0.35rem 0.35rem; text-align: left; border-radius: 12px; background: var(--bg-2); }
  .lrow.off { opacity: 0.45; }
  .lm { width: 96px; flex: none; border-radius: 8px; overflow: hidden; }
  .lt { display: grid; gap: 0.15rem; flex: 1; min-width: 0; }
  .lt strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 0.92rem; }
  .sd { display: inline-block; width: 7px; height: 7px; border-radius: 50%; background: var(--sys); margin-right: 0.3rem; }
  .badge.live { color: var(--ok); }
</style>
