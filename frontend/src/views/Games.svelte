<script lang="ts">
  import { SYSTEM_SHORT } from '../lib/format';
  import { app } from '../lib/state.svelte';
  import type { Game } from '../lib/types';
  import GameSheet from './GameSheet.svelte';

  const PREFS = 'naomox.games.filters';
  type Prefs = { systems: string[]; favOnly: boolean; installedOnly: boolean; showDisabled: boolean };
  function loadPrefs(): Prefs {
    const d: Prefs = { systems: [], favOnly: false, installedOnly: true, showDisabled: false };
    try {
      return { ...d, ...JSON.parse(localStorage.getItem(PREFS) ?? '{}') };
    } catch {
      return d;
    }
  }

  const prefs = $state<Prefs>(loadPrefs());
  let query = $state('');
  let selected = $state<Game | null>(null);
  let sheetOpen = $state(false);

  $effect(() => {
    try {
      localStorage.setItem(PREFS, JSON.stringify(prefs));
    } catch {
      /* stockage indisponible */
    }
  });

  const systems = $derived([...new Set(app.games.map((g) => g.system))].sort());
  const installedCount = $derived(app.games.filter((g) => g.present).length);

  const visible = $derived.by(() => {
    const q = query.trim().toLowerCase();
    return app.games.filter(
      (g) =>
        (prefs.showDisabled || g.enabled) &&
        (!prefs.installedOnly || g.present) &&
        (!prefs.favOnly || g.favourite) &&
        (!prefs.systems.length || prefs.systems.includes(g.system)) &&
        (!q || g.name.toLowerCase().includes(q) || g.rom.toLowerCase().includes(q) || g.genre?.toLowerCase().includes(q)),
    );
  });

  function toggleSystem(s: string) {
    prefs.systems = prefs.systems.includes(s) ? prefs.systems.filter((x) => x !== s) : [...prefs.systems, s];
  }

  function open(g: Game) {
    selected = g;
    sheetOpen = true;
  }

  function initials(name: string) {
    return name.split(/\s+/).slice(0, 2).map((w) => w[0]).join('').toUpperCase();
  }
</script>

<div class="page">
  <div class="search">
    <input type="search" placeholder="Rechercher un jeu…" bind:value={query} aria-label="Rechercher" />
  </div>
  <div class="chips">
    <button class="chip" class:on={prefs.favOnly} onclick={() => (prefs.favOnly = !prefs.favOnly)}>★ Favoris</button>
    {#each systems as s (s)}
      <button class="chip" class:on={prefs.systems.includes(s)} onclick={() => toggleSystem(s)}>{SYSTEM_SHORT[s] ?? s}</button>
    {/each}
    <button class="chip" class:on={!prefs.installedOnly} onclick={() => (prefs.installedOnly = !prefs.installedOnly)}>
      Non installés
    </button>
    <button class="chip" class:on={prefs.showDisabled} onclick={() => (prefs.showDisabled = !prefs.showDisabled)}>Désactivés</button>
  </div>

  {#if !app.games.length}
    <p class="empty">Aucun jeu.</p>
  {:else if !installedCount && prefs.installedOnly}
    <div class="empty">
      <p>Aucune ROM installée sur le serveur.</p>
      <p class="small">Copiez les fichiers <code>.bin.gz</code> dans <code>/srv/naomox/roms</code> ou utilisez <a href="#/reglages">Réglages → Fichiers</a>.</p>
    </div>
  {:else if !visible.length}
    <p class="empty">Aucun jeu ne correspond aux filtres.</p>
  {:else}
    <p class="muted small count">{visible.length} jeu{visible.length > 1 ? 'x' : ''}</p>
    <div class="grid">
      {#each visible as g (g.rom)}
        <button class="game" class:missing={!g.present} class:disabled={!g.enabled} onclick={() => open(g)}>
          <div class="art">
            {#if g.image}<img src={g.image} alt="" loading="lazy" />{:else}<span>{initials(g.name)}</span>{/if}
            {#if g.favourite}<i class="fav">★</i>{/if}
          </div>
          <div class="meta">
            <span class="title">{g.name}</span>
            <span class="badge">{SYSTEM_SHORT[g.system] ?? g.system}</span>
          </div>
        </button>
      {/each}
    </div>
  {/if}
</div>

{#if selected}
  <GameSheet bind:open={sheetOpen} rom={selected.rom} />
{/if}

<style>
  .search { position: sticky; top: 60px; z-index: 5; }
  .chips { display: flex; gap: 0.4rem; overflow-x: auto; padding: 0.7rem 0 0.2rem; scrollbar-width: none; }
  .chip { min-height: 36px; padding: 0.25rem 0.8rem; border-radius: 99px; white-space: nowrap; font-size: 0.9rem; }
  .chip.on { background: var(--accent); color: var(--accent-fg); border-color: transparent; }
  .count { margin: 0.5rem 0; }
  .grid { display: grid; gap: 0.7rem; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); }
  .game {
    display: grid; padding: 0; text-align: left; overflow: hidden; align-items: stretch;
    background: var(--bg-2); border-radius: var(--radius); min-height: 0;
  }
  .game.missing, .game.disabled { opacity: 0.45; }
  .art { position: relative; aspect-ratio: 4 / 3; background: var(--bg-3); display: grid; place-items: center; }
  .art img { width: 100%; height: 100%; object-fit: cover; }
  .art span { font-size: 1.8rem; font-weight: 800; color: var(--fg-2); }
  .fav { position: absolute; top: 6px; right: 8px; color: var(--accent); font-style: normal; text-shadow: 0 1px 3px #000; }
  .meta { display: grid; gap: 0.3rem; padding: 0.55rem 0.65rem 0.7rem; }
  .title { font-weight: 600; font-size: 0.92rem; line-height: 1.2; display: -webkit-box; -webkit-line-clamp: 2; line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
  .meta .badge { justify-self: start; }
</style>
