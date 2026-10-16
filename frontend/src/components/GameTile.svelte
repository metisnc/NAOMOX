<script lang="ts">
  // Tuile de jeu simplifiée : grand rectangle arrondi = fronton du logo + nom sur une ligne.
  import { displayName, systemColor, variants } from '../lib/catalog';
  import type { Game } from '../lib/types';
  import Marquee from './Marquee.svelte';

  let { game, playingOn = [], onopen }: { game: Game; playingOn?: string[]; onopen: (g: Game) => void } = $props();

  let hover = $state(false);
  const name = $derived(displayName(game));
  const vs = $derived(variants(game));
</script>

<button
  class="tile"
  class:off={!game.present || !game.enabled}
  style="--sys:{systemColor(game.system)}"
  onclick={() => onopen(game)}
  onpointerenter={() => (hover = true)}
  onpointerleave={() => (hover = false)}
  aria-label={name + (vs.length ? ` (${vs.join(', ')})` : '')}
>
  <span class="art"><Marquee image={game.image} {name} system={game.system} lit={hover} /></span>
  <span class="label">
    <span class="name">{name}</span>
    {#each vs as v (v)}<b class="var">{v}</b>{/each}
    {#if game.favourite}<span class="fav" aria-label="Favori">★</span>{/if}
  </span>
  {#if playingOn.length}<span class="live" title={'En cours sur ' + playingOn.join(', ')}><i></i>{playingOn[0]}</span>{/if}
</button>

<style>
  .tile {
    position: relative;
    display: grid;
    grid-template-rows: auto auto;
    grid-template-columns: minmax(0, 1fr);
    width: 100%;
    min-height: 0;
    padding: 0;
    text-align: left;
    border-radius: 18px;
    border: 1px solid var(--line);
    background: var(--bg-2);
    overflow: hidden;
    transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s;
  }
  .tile:hover, .tile:focus-visible {
    transform: translateY(-2px);
    border-color: color-mix(in srgb, var(--sys) 70%, var(--line));
    box-shadow: 0 10px 26px -12px color-mix(in srgb, var(--sys) 80%, transparent);
  }
  .tile:active { transform: scale(0.985); }
  .tile.off { opacity: 0.42; filter: grayscale(0.6); }
  .art { display: block; width: 100%; }
  .art :global(.marquee) { aspect-ratio: 3 / 1; border-radius: 0; }
  .label {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.4rem;
    min-width: 0;
    padding: 0.55rem 0.8rem 0.6rem;
    border-top: 2px solid color-mix(in srgb, var(--sys) 55%, transparent);
  }
  .name { flex: 0 1 auto; min-width: 0; text-align: center; font-weight: 700; font-size: 0.95rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .var {
    flex: none; font-size: 0.66rem; font-weight: 700; padding: 0.08rem 0.45rem; border-radius: 99px;
    background: color-mix(in srgb, var(--sys) 22%, var(--bg-3));
  }
  .fav { flex: none; color: var(--neon-gold); text-shadow: 0 0 6px color-mix(in srgb, var(--neon-gold) 60%, transparent); }
  .live {
    position: absolute; top: 8px; left: 8px; display: inline-flex; align-items: center; gap: 0.3rem;
    max-width: 70%; padding: 0.1rem 0.5rem; border-radius: 99px; font-size: 0.7rem; font-weight: 700;
    background: rgb(0 0 0 / 0.72); color: #fff; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }
  .live i { width: 7px; height: 7px; border-radius: 50%; background: var(--ok); animation: pulse 1.4s infinite; }
  @keyframes pulse { 50% { opacity: 0.3; } }
</style>
