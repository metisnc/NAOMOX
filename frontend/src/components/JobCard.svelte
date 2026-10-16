<script lang="ts">
  import { api } from '../lib/api';
  import { displayName } from '../lib/catalog';
  import { ERROR_HELP, isFinal, romLabel } from '../lib/format';
  import { jobMessage, jobPercent, jobTone } from '../lib/progress';
  import { app } from '../lib/state.svelte';
  import type { Job } from '../lib/types';
  import ProgressBar from './ProgressBar.svelte';

  let { job, compact = false }: { job: Job; compact?: boolean } = $props();
  let showLog = $state(false);
  let log = $state<string[]>([]);

  const game = $derived(app.games.find((g) => g.rom === job.rom));
  const title = $derived(game ? displayName(game) : romLabel(job.rom, app.names));

  async function toggleLog() {
    showLog = !showLog;
    if (showLog) log = (await api.get<Job>(`/jobs/${job.id}`)).log ?? [];
  }
</script>

<div class="job" class:compact>
  <div class="head">
    <strong>{title}</strong>
    {#if job.source !== 'user'}<span class="src">{job.source === 'server' ? 'mode serveur' : 'démarrage auto'}</span>{/if}
  </div>
  <p class="launch-msg {jobTone(job)}">{jobMessage(job)}</p>
  {#if !isFinal(job)}<ProgressBar value={jobPercent(job)} size={compact ? 'sm' : 'md'} />{/if}
  {#if job.state === 'error' && job.error_kind && ERROR_HELP[job.error_kind]}
    <p class="help">{ERROR_HELP[job.error_kind]}</p>
  {/if}
  {#if !compact}
    <div class="pills">
      {#if !isFinal(job)}
        <button class="pill" onclick={() => app.run(() => api.post(`/jobs/${job.id}/cancel`))}>Annuler</button>
      {:else if job.state !== 'done'}
        <button class="pill primary" onclick={() => app.run(() => api.post(`/jobs/${job.id}/retry`), 'Relancé')}>Réessayer</button>
      {/if}
      <button class="pill ghost" onclick={toggleLog}>{showLog ? 'Masquer le journal' : 'Journal'}</button>
    </div>
    {#if showLog}<pre class="launch-log">{log.join('\n') || '(vide)'}</pre>{/if}
  {/if}
</div>

<style>
  .job {
    display: grid;
    gap: 0.45rem;
    padding: 0.8rem 0.9rem;
    border-radius: 14px;
    background: var(--neon-panel);
    border: 1px solid var(--neon-line);
    color: var(--neon-text);
  }
  .job.compact { padding: 0.55rem 0.8rem; gap: 0.3rem; }
  .head { display: flex; align-items: baseline; gap: 0.5rem; min-width: 0; }
  .head strong { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .src { font-size: 0.72rem; color: var(--neon-muted); white-space: nowrap; }
  .help { margin: 0; font-size: 0.82rem; color: var(--neon-muted); }
</style>
