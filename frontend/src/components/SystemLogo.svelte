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
  /* Toutes les pastilles ont la même taille ; le logo s'y loge en « contain ». */
  .logo {
    display: inline-grid;
    place-items: center;
    width: 116px;
    height: 38px;
    padding: 3px 10px 4px;
    box-sizing: border-box;
    flex: none;
    border-radius: 99px;
    background: #f7f8fc;
    box-shadow: inset 0 -2px 0 var(--sys);
  }
  .logo.sm { width: 70px; height: 22px; padding: 3px 8px; box-shadow: inset 0 -1.5px 0 var(--sys); }
  .logo img { width: 100%; height: 100%; object-fit: contain; }
  .text { display: inline-flex; align-items: center; gap: 0.35rem; font-weight: 700; font-size: 0.85rem; }
  .text.sm { font-size: 0.72rem; }
  .text i { width: 8px; height: 8px; border-radius: 50%; background: var(--sys); box-shadow: 0 0 6px var(--sys); }
</style>
