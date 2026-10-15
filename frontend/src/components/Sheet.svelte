<script lang="ts">
  import type { Snippet } from 'svelte';

  let { open = $bindable(false), title = '', children }: { open: boolean; title?: string; children: Snippet } = $props();

  function onKey(e: KeyboardEvent) {
    if (e.key === 'Escape') open = false;
  }
</script>

<svelte:window onkeydown={onKey} />

{#if open}
  <div class="backdrop" role="presentation" onclick={() => (open = false)}></div>
  <div class="sheet" role="dialog" aria-modal="true" aria-label={title}>
    <div class="head">
      <h3>{title}</h3>
      <button class="ghost small" onclick={() => (open = false)} aria-label="Fermer">✕</button>
    </div>
    <div class="body">{@render children()}</div>
  </div>
{/if}

<style>
  .backdrop { position: fixed; inset: 0; background: rgb(0 0 0 / 0.55); z-index: 50; }
  .sheet {
    position: fixed; z-index: 51; left: 0; right: 0; bottom: 0;
    max-height: 92dvh; overflow: auto;
    background: var(--bg-2); border-top-left-radius: 20px; border-top-right-radius: 20px;
    border: 1px solid var(--line); padding-bottom: calc(var(--safe-b) + 1rem);
    animation: up 0.18s ease-out;
  }
  .head {
    position: sticky; top: 0; display: flex; justify-content: space-between; align-items: center;
    padding: 0.8rem 1rem; background: var(--bg-2); border-bottom: 1px solid var(--line);
  }
  .body { padding: 1rem; }
  @media (min-width: 760px) {
    .sheet { left: 50%; bottom: auto; top: 50%; transform: translate(-50%, -50%); width: 620px; border-radius: 20px; animation: none; }
  }
  @keyframes up { from { transform: translateY(30%); opacity: 0.5; } }
</style>
