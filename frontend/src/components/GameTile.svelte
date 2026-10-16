<script lang="ts">
  import { genreIcon, genreLabel, systemColor, systemShort, variants, displayName } from '../lib/catalog';
  import type { Game } from '../lib/types';
  import Marquee from './Marquee.svelte';

  let {
    game,
    playingOn = [],
    onopen,
    compact = false,
  }: { game: Game; playingOn?: string[]; onopen: (g: Game) => void; compact?: boolean } = $props();

  let hover = $state(false);
  const vs = $derived(variants(game));
</script>

<button
  class="tile"
  class:compact
  class:off={!game.present || !game.enabled}
  style="--sys:{systemColor(game.system)}"
  onclick={() => onopen(game)}
  onpointerenter={() => (hover = true)}
  onpointerleave={() => (hover = false)}
  aria-label={game.name}
>
  <Marquee image={game.image} name={displayName(game)} system={game.system} size={compact ? 'sm' : 'md'} lit={hover} />
  {#if game.favourite}<span class="fav" aria-label="Favori">★</span>{/if}
  {#if playingOn.length}<span class="live" title={'En cours sur ' + playingOn.join(', ')}><i></i>{playingOn[0]}</span>{/if}
  {#if !compact}
    <span class="info">
      <span class="name">{displayName(game)}</span>
      {#if vs.length}<span class="vars">{#each vs as v (v)}<b>{v}</b>{/each}</span>{/if}
      <span class="meta">
        <span class="sys"><i></i>{systemShort(game.system)}</span>
        {#if game.year}<span>{game.year}</span>{/if}
        {#if game.genre}<span title={genreLabel(game.genre)}>{genreIcon(game.genre)} {genreLabel(game.genre)}</span>{/if}
      </span>
    </span>
  {/if}
</button>

<style>
  .tile {
    position: relative;
    display: grid;
    grid-template-rows: auto 1fr;
    padding: 0;
    min-height: 0;
    width: 100%;
    text-align: left;
    border-radius: 14px;
    border: 1px solid var(--line);
    background: var(--bg-2);
    overflow: hidden;
    transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s;
  }
  .tile:hover, .tile:focus-visible {
    transform: translateY(-3px);
    border-color: color-mix(in srgb, var(--sys) 60%, var(--line));
    box-shadow: 0 10px 28px -10px color-mix(in srgb, var(--sys) 65%, transparent);
  }
  .tile:active { transform: scale(0.98); }
  .tile.off { opacity: 0.42; filter: grayscale(0.6); }
  .info { display: grid; gap: 0.3rem; padding: 0.55rem 0.7rem 0.7rem; align-content: start; }
  .name {
    font-weight: 650;
    font-size: 0.9rem;
    line-height: 1.2;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
  .vars { display: flex; flex-wrap: wrap; gap: 0.25rem; }
  .vars b { font-size: 0.66rem; font-weight: 700; padding: 0.05rem 0.4rem; border-radius: 99px; background: color-mix(in srgb, var(--sys) 22%, var(--bg-3)); color: var(--fg); }
  .meta { display: flex; flex-wrap: wrap; gap: 0.25rem 0.6rem; font-size: 0.72rem; color: var(--fg-2); }
  .sys { display: inline-flex; align-items: center; gap: 0.3rem; color: var(--fg); font-weight: 600; }
  .sys i { width: 7px; height: 7px; border-radius: 50%; background: var(--sys); box-shadow: 0 0 6px var(--sys); }
  .fav {
    position: absolute; top: 6px; right: 8px;
    color: var(--neon-gold); font-size: 1rem; text-shadow: 0 1px 4px rgb(0 0 0 / 0.8);
  }
  .live {
    position: absolute; top: 6px; left: 6px; display: inline-flex; align-items: center; gap: 0.3rem;
    max-width: 75%; padding: 0.1rem 0.45rem; border-radius: 99px; font-size: 0.68rem; font-weight: 700;
    background: rgb(0 0 0 / 0.72); color: #fff; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }
  .live i { width: 7px; height: 7px; border-radius: 50%; background: var(--ok); animation: pulse 1.4s infinite; }
  @keyframes pulse { 50% { opacity: 0.3; } }
</style>
