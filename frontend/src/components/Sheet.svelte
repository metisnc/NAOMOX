<script lang="ts">
  import type { Snippet } from 'svelte';

  let {
    open = $bindable(false),
    title = '',
    wide = false,
    bare = false,
    children,
  }: { open: boolean; title?: string; wide?: boolean; bare?: boolean; children: Snippet } = $props();

  let sheet = $state<HTMLDivElement | null>(null);
  let dragY = $state(0);
  let startY: number | null = null;

  function onKey(e: KeyboardEvent) {
    if (e.key === 'Escape') open = false;
  }

  // Glisser vers le bas depuis la poignée pour fermer (mobile).
  function down(e: PointerEvent) {
    startY = e.clientY;
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
  }
  function move(e: PointerEvent) {
    if (startY !== null) dragY = Math.max(0, e.clientY - startY);
  }
  function up() {
    if (dragY > 110) open = false;
    dragY = 0;
    startY = null;
  }

  $effect(() => {
    if (open) {
      const prev = document.body.style.overflow;
      document.body.style.overflow = 'hidden';
      return () => (document.body.style.overflow = prev);
    }
  });

  export function scrollTop() {
    sheet?.scrollTo({ top: 0, behavior: 'smooth' });
  }
</script>

<svelte:window onkeydown={onKey} />

{#if open}
  <div class="backdrop" role="presentation" onclick={() => (open = false)}></div>
  <div
    class="sheet"
    class:wide
    class:bare
    bind:this={sheet}
    role="dialog"
    aria-modal="true"
    aria-label={title}
    style={dragY ? `transform: translateY(${dragY}px); transition: none` : ''}
  >
    <div class="grip" role="presentation" onpointerdown={down} onpointermove={move} onpointerup={up} onpointercancel={up}><span></span></div>
    {#if bare}
      <button class="close" onclick={() => (open = false)} aria-label="Fermer">✕</button>
    {:else}
      <div class="head">
        <h3>{title}</h3>
        <button class="ghost small" onclick={() => (open = false)} aria-label="Fermer">✕</button>
      </div>
    {/if}
    <div class="body">{@render children()}</div>
  </div>
{/if}

<style>
  .backdrop { position: fixed; inset: 0; background: rgb(0 0 0 / 0.6); backdrop-filter: blur(3px); z-index: 50; animation: fade 0.2s; }
  .sheet {
    position: fixed; z-index: 51; left: 0; right: 0; bottom: 0;
    max-height: 94dvh; overflow: auto; overscroll-behavior: contain;
    background: var(--bg-2); border-top-left-radius: 22px; border-top-right-radius: 22px;
    border: 1px solid var(--line); padding-bottom: calc(var(--safe-b) + 1rem);
    animation: up 0.24s cubic-bezier(0.2, 0.9, 0.3, 1.1);
    transition: transform 0.2s;
  }
  .grip { position: sticky; top: 0; z-index: 3; height: 18px; display: grid; place-items: center; cursor: grab; touch-action: none; }
  .grip span { width: 42px; height: 5px; border-radius: 99px; background: var(--line); }
  .bare .grip { position: absolute; left: 0; right: 0; }
  .bare .grip span { background: rgb(255 255 255 / 0.5); }
  .head {
    position: sticky; top: 18px; z-index: 2; display: flex; justify-content: space-between; align-items: center;
    padding: 0 1rem 0.7rem; background: var(--bg-2); border-bottom: 1px solid var(--line);
  }
  .close {
    position: absolute; top: 14px; right: 14px; z-index: 4; width: 38px; min-height: 38px; padding: 0;
    border-radius: 50%; background: rgb(0 0 0 / 0.55); color: #fff; border-color: rgb(255 255 255 / 0.2); backdrop-filter: blur(6px);
  }
  .body { padding: 1rem; }
  .bare .body { padding: 0 0 1rem; }
  @media (min-width: 760px) {
    .sheet { left: 50%; bottom: auto; top: 50%; translate: -50% -50%; width: 620px; border-radius: 22px; animation: pop 0.2s ease-out; }
    .sheet.wide { width: min(980px, 94vw); }
    .grip { display: none; }
  }
  @keyframes up { from { transform: translateY(40%); opacity: 0.4; } }
  @keyframes pop { from { opacity: 0; scale: 0.96; } }
  @keyframes fade { from { opacity: 0; } }
</style>
