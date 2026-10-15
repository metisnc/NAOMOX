<script lang="ts">
  import { app } from '../lib/state.svelte';
</script>

<div class="toasts" aria-live="polite">
  {#each app.toasts as t (t.id)}
    <div class="toast {t.kind}">{t.text}</div>
  {/each}
</div>

<style>
  .toasts {
    position: fixed; left: 50%; transform: translateX(-50%); z-index: 100;
    bottom: calc(var(--nav-h) + var(--safe-b) + 12px);
    display: grid; gap: 0.5rem; width: min(92vw, 460px); pointer-events: none;
  }
  .toast {
    background: var(--bg-3); border: 1px solid var(--line); border-left: 4px solid var(--fg-2);
    padding: 0.7rem 0.9rem; border-radius: 10px; box-shadow: 0 6px 24px rgb(0 0 0 / 0.35);
  }
  .toast.ok { border-left-color: var(--ok); }
  .toast.error { border-left-color: var(--err); }
</style>
