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
      {#if onmore}<button class="ghost small" onclick={onmore}>Tout voir ›</button>{/if}
    </header>
    <div class="row" role="list">
      {#each games as g (g.rom)}
        <div class="cell" role="listitem"><GameTile game={g} playingOn={playing.get(g.rom)} {onopen} /></div>
      {/each}
    </div>
  </section>
{/if}

<style>
  .shelf { margin: 0.4rem 0 1.1rem; }
  header { display: flex; align-items: baseline; justify-content: space-between; }
  h2 { margin: 0 0 0.5rem; color: var(--fg); font-size: 1.05rem; }
  .row {
    display: grid; grid-auto-flow: column; grid-auto-columns: minmax(158px, 44%);
    gap: 0.65rem; overflow-x: auto; scroll-snap-type: x mandatory; padding: 0.2rem 0.1rem 0.6rem;
    scrollbar-width: none; overscroll-behavior-x: contain;
  }
  .row::-webkit-scrollbar { display: none; }
  .cell { scroll-snap-align: start; display: grid; }
  @media (min-width: 700px) { .row { grid-auto-columns: 210px; } }
</style>
