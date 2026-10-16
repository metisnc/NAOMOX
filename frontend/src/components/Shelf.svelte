<script lang="ts">
  import type { Game } from '../lib/types';
  import GameTile from './GameTile.svelte';

  let {
    title,
    games,
    playing,
    onopen,
    onmore,
  }: {
    title: string;
    games: Game[];
    playing: Map<string, string[]>;
    onopen: (g: Game) => void;
    onmore?: () => void;
  } = $props();
</script>

{#if games.length}
  <section class="shelf">
    <header>
      <h2>{title}</h2>
      {#if onmore}<button class="ghost small more" onclick={onmore}>Tout voir ›</button>{/if}
    </header>
    <div class="row" role="list">
      {#each games as g (g.rom)}
        <div class="cell" role="listitem"><GameTile game={g} playingOn={playing.get(g.rom)} {onopen} /></div>
      {/each}
    </div>
  </section>
{/if}

<style>
  .shelf { margin: 0 0 0.55rem; }
  header { display: flex; align-items: center; justify-content: space-between; min-height: 34px; }
  h2 { margin: 0; color: var(--fg); font-size: 1rem; }
  .more { min-height: 30px; color: var(--accent); }
  .row {
    display: grid; grid-auto-flow: column; grid-auto-columns: 80%;
    gap: 0.6rem; overflow-x: auto; scroll-snap-type: x mandatory; padding: 0.15rem 0.1rem 0.35rem;
    scrollbar-width: none; overscroll-behavior-x: contain;
  }
  .row::-webkit-scrollbar { display: none; }
  .cell { scroll-snap-align: start; display: grid; }
  @media (min-width: 600px) { .row { grid-auto-columns: 300px; } }
</style>
