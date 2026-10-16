<script lang="ts">
  // Logo officiel du système (Naomi, Chihiro…) sur une pastille claire, ou nom en repli
  // quand le logo n'est pas installé dans /srv/naomox/media/systems.
  import { systemColor, systemShort } from '../lib/catalog';
  import { app } from '../lib/state.svelte';

  let { system, size = 'md' }: { system: string; size?: 'sm' | 'md' } = $props();

  const url = $derived(app.systems?.logos?.[system] ?? null);
  let failed = $state(false);
</script>

{#if url && !failed}
  <span class="logo {size}" style="--sys:{systemColor(system)}">
    <img src={url} alt={systemShort(system)} onerror={() => (failed = true)} />
  </span>
{:else}
  <span class="text {size}" style="--sys:{systemColor(system)}"><i></i>{systemShort(system)}</span>
{/if}

<style>
  .logo {
    display: inline-grid;
    place-items: center;
    height: 30px;
    padding: 4px 10px;
    border-radius: 99px;
    background: #f7f8fc;
    box-shadow: inset 0 -2px 0 var(--sys);
  }
  .logo.sm { height: 20px; padding: 2px 7px; box-shadow: inset 0 -1.5px 0 var(--sys); }
  .logo img { height: 100%; max-width: 92px; object-fit: contain; }
  .logo.sm img { max-width: 62px; }
  .text { display: inline-flex; align-items: center; gap: 0.35rem; font-weight: 700; font-size: 0.85rem; }
  .text.sm { font-size: 0.72rem; }
  .text i { width: 8px; height: 8px; border-radius: 50%; background: var(--sys); box-shadow: 0 0 6px var(--sys); }
</style>
