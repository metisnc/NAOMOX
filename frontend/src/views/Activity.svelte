<script lang="ts">
  import { onMount } from 'svelte';
  import JobCard from '../components/JobCard.svelte';
  import { api } from '../lib/api';
  import { STATE_LABEL, ago, romLabel } from '../lib/format';
  import { app } from '../lib/state.svelte';
  import type { HistoryEntry, JobState } from '../lib/types';

  let history = $state<HistoryEntry[]>([]);

  async function load() {
    history = (await app.run(() => api.get<HistoryEntry[]>('/history?limit=100'))) ?? [];
  }

  onMount(load);

  // Recharge l'historique quand un job se termine.
  let lastActive = $state(0);
  $effect(() => {
    const n = app.activeJobs.length;
    if (n < lastActive) load();
    lastActive = n;
  });

  const recentFailed = $derived(
    Object.values(app.jobs)
      .filter((j) => j.state === 'error')
      .sort((a, b) => (b.ended ?? 0) - (a.ended ?? 0))
      .slice(0, 3),
  );
</script>

<div class="page">
  <h1>Activité</h1>

  <h2>En cours</h2>
  {#if app.activeJobs.length}
    <div class="stack">{#each app.activeJobs as job (job.id)}<JobCard {job} />{/each}</div>
  {:else}
    <p class="muted">Aucun transfert en cours.</p>
  {/if}

  {#if recentFailed.length}
    <h2>Échecs récents</h2>
    <div class="stack">{#each recentFailed as job (job.id)}<JobCard {job} />{/each}</div>
  {/if}

  <h2>Historique</h2>
  {#if !history.length}
    <p class="muted">Aucun lancement pour l’instant.</p>
  {:else}
    <ul class="history">
      {#each history as h (h.job + h.ts)}
        <li class={h.state}>
          <div class="row">
            <strong class="grow">{romLabel(h.rom, app.names)}</strong>
            <span class="badge">{STATE_LABEL[h.state as JobState] ?? h.state}</span>
          </div>
          <div class="muted small">
            {h.cabinet} · {ago(h.ts)} · {h.duration} s
            {#if h.source !== 'user'}· {h.source === 'server' ? 'mode serveur' : 'démarrage auto'}{/if}
            {#if h.kind !== 'launch'}· {h.kind}{/if}
          </div>
          {#if h.state === 'error' && h.message}<div class="small err">{h.message}</div>{/if}
        </li>
      {/each}
    </ul>
  {/if}
</div>

<style>
  .history { list-style: none; padding: 0; margin: 0; display: grid; gap: 0.5rem; }
  .history li { background: var(--bg-2); border: 1px solid var(--line); border-radius: 12px; padding: 0.65rem 0.85rem; }
  .history li.done .badge { color: var(--ok); }
  .history li.error .badge, .err { color: var(--err); }
</style>
