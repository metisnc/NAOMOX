<script lang="ts">
  import Sheet from '../components/Sheet.svelte';
  import {
    SORTS,
    controlsLabel,
    facet,
    genreIcon,
    genreLabel,
    publisher,
    ratingInfo,
    ratingKey,
    systemColor,
    systemShort,
  } from '../lib/catalog';
  import { browse } from '../lib/browse.svelte';
  import { app } from '../lib/state.svelte';

  let { open = $bindable(false), resultCount }: { open: boolean; resultCount: number } = $props();

  let allPublishers = $state(false);

  // Facettes calculées sur les jeux visibles par défaut (installés, activés).
  const base = $derived(app.games.filter((g) => (browse.filters.installedOnly ? g.present : true) && (browse.filters.showDisabled || g.enabled)));
  const systems = $derived(facet(base, (g) => g.system));
  const genres = $derived(facet(base, (g) => g.genre));
  const controls = $derived(facet(base, (g) => g.controls));
  const publishers = $derived(facet(base, (g) => publisher(g.manufacturer)));
  const ratings = $derived(facet(base, (g) => (g.rating ? ratingKey(g.rating) : '')));
  const years = $derived([...new Set(base.map((g) => Number(g.year)).filter(Boolean))].sort((a, b) => a - b));
  const ratingColor = (label: string) =>
    ratingInfo(app.games.find((g) => g.rating && ratingKey(g.rating) === label)?.rating ?? '')?.color ?? '#9aa5b1';

  $effect(() => {
    // Toute modification est mémorisée.
    void JSON.stringify(browse.filters);
    void browse.sort;
    void browse.favFirst;
    browse.save();
  });
</script>

<Sheet bind:open title="Trier et filtrer">
  <div class="panel">
    <section>
      <h4>Trier par</h4>
      <div class="chips">
        {#each SORTS as s (s.key)}
          <button class="chip" class:on={browse.sort === s.key} onclick={() => (browse.sort = s.key)}>{s.label}</button>
        {/each}
      </div>
      <label class="check"><input type="checkbox" bind:checked={browse.favFirst} /> Favoris en premier</label>
    </section>

    <section>
      <h4>Système</h4>
      <div class="chips">
        {#each systems as f (f.value)}
          <button class="chip sys" style="--c:{systemColor(f.value)}" class:on={browse.filters.systems.includes(f.value)} onclick={() => browse.toggle('systems', f.value)}>
            <i></i>{systemShort(f.value)} <small>{f.count}</small>
          </button>
        {/each}
      </div>
    </section>

    {#if app.cabinets.length}
      <section>
        <h4>Compatible avec la borne</h4>
        <div class="chips">
          <button class="chip" class:on={!browse.filters.cabinet} onclick={() => (browse.filters.cabinet = null)}>Toutes</button>
          {#each app.cabinets as c (c.id)}
            <button class="chip" class:on={browse.filters.cabinet === c.id} onclick={() => (browse.filters.cabinet = c.id)}>
              <span class="dot" class:on={c.status.online === true} class:off={c.status.online === false}></span>{c.name}
            </button>
          {/each}
        </div>
      </section>
    {/if}

    <section>
      <h4>Genre</h4>
      <div class="chips">
        {#each genres as f (f.value)}
          <button class="chip" class:on={browse.filters.genres.includes(f.value)} onclick={() => browse.toggle('genres', f.value)}>
            {genreIcon(f.value)} {genreLabel(f.value)} <small>{f.count}</small>
          </button>
        {/each}
      </div>
    </section>

    <section>
      <h4>Commandes</h4>
      <div class="chips">
        {#each controls as f (f.value)}
          <button class="chip" class:on={browse.filters.controls.includes(f.value)} onclick={() => browse.toggle('controls', f.value)}>
            {controlsLabel(f.value)} <small>{f.count}</small>
          </button>
        {/each}
      </div>
    </section>

    <section class="two">
      <div>
        <h4>Orientation de l’écran</h4>
        <div class="seg">
          <button class:on={browse.filters.orientation === ''} onclick={() => (browse.filters.orientation = '')}>Toutes</button>
          <button class:on={browse.filters.orientation === 'Horizontal'} onclick={() => (browse.filters.orientation = 'Horizontal')}>▭ Horizontal</button>
          <button class:on={browse.filters.orientation === 'Vertical'} onclick={() => (browse.filters.orientation = 'Vertical')}>▯ Vertical</button>
        </div>
      </div>
      <div>
        <h4>Années</h4>
        <div class="row years">
          <select bind:value={browse.filters.yearMin} aria-label="Année minimale">
            <option value={null}>depuis…</option>
            {#each years as y (y)}<option value={y}>{y}</option>{/each}
          </select>
          <span>→</span>
          <select bind:value={browse.filters.yearMax} aria-label="Année maximale">
            <option value={null}>jusqu’à…</option>
            {#each years as y (y)}<option value={y}>{y}</option>{/each}
          </select>
        </div>
      </div>
    </section>

    <section>
      <h4>Éditeur</h4>
      <div class="chips">
        {#each allPublishers ? publishers : publishers.slice(0, 10) as f (f.value)}
          <button class="chip" class:on={browse.filters.publishers.includes(f.value)} onclick={() => browse.toggle('publishers', f.value)}>
            {f.value} <small>{f.count}</small>
          </button>
        {/each}
        {#if publishers.length > 10}
          <button class="chip ghost" onclick={() => (allPublishers = !allPublishers)}>{allPublishers ? 'Moins' : `+ ${publishers.length - 10} autres`}</button>
        {/if}
      </div>
    </section>

    <section>
      <h4>Classification</h4>
      <div class="chips">
        {#each ratings as f (f.value)}
          <button class="chip sys" style="--c:{ratingColor(f.value)}" class:on={browse.filters.ratings.includes(f.value)} onclick={() => browse.toggle('ratings', f.value)}>
            <i></i>{f.value} <small>{f.count}</small>
          </button>
        {/each}
      </div>
    </section>

    <section>
      <h4>Afficher</h4>
      <label class="check"><input type="checkbox" bind:checked={browse.filters.favOnly} /> Seulement les favoris</label>
      <label class="check"><input type="checkbox" bind:checked={browse.filters.playedOnly} /> Seulement les jeux déjà lancés</label>
      <label class="check"><input type="checkbox" checked={!browse.filters.installedOnly} onchange={(e) => (browse.filters.installedOnly = !e.currentTarget.checked)} /> Inclure les jeux sans ROM</label>
      <label class="check"><input type="checkbox" bind:checked={browse.filters.showDisabled} /> Inclure les jeux désactivés</label>
    </section>
  </div>

  <footer>
    <button onclick={() => browse.reset()}>Réinitialiser</button>
    <button class="primary grow" onclick={() => (open = false)}>Voir {resultCount} jeu{resultCount > 1 ? 'x' : ''}</button>
  </footer>
</Sheet>

<style>
  .panel { display: grid; gap: 1.1rem; padding-bottom: 4.5rem; }
  h4 { margin: 0 0 0.5rem; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.08em; color: var(--fg-2); }
  .chips { display: flex; flex-wrap: wrap; gap: 0.4rem; }
  .chip { min-height: 36px; padding: 0.25rem 0.75rem; border-radius: 99px; font-size: 0.88rem; }
  .chip small { color: var(--fg-2); font-size: 0.72rem; margin-left: 0.15rem; }
  .chip.on { background: var(--accent); color: var(--accent-fg); border-color: transparent; }
  .chip.on small { color: inherit; opacity: 0.7; }
  .chip.sys i { width: 9px; height: 9px; border-radius: 50%; background: var(--c); }
  .chip.sys.on { background: var(--c); color: #111; }
  .chip.sys.on i { background: #111; }
  .chip .dot { margin-right: 0.15rem; }
  .seg { display: inline-flex; border: 1px solid var(--line); border-radius: 10px; overflow: hidden; }
  .seg button { border: 0; border-radius: 0; min-height: 38px; font-size: 0.88rem; background: transparent; }
  .seg button.on { background: var(--accent); color: var(--accent-fg); }
  .two { display: grid; gap: 1.1rem; }
  @media (min-width: 560px) { .two { grid-template-columns: auto 1fr; } }
  .years select { width: auto; flex: 1; }
  footer {
    position: sticky; bottom: calc(-1 * (var(--safe-b) + 1rem)); display: flex; gap: 0.6rem;
    margin: 0 -1rem calc(-1 * (var(--safe-b) + 1rem)); padding: 0.75rem 1rem calc(var(--safe-b) + 0.75rem);
    background: var(--bg-2); border-top: 1px solid var(--line);
  }
</style>
