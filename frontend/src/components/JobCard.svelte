<script lang="ts">
  import { api } from '../lib/api';
  import { ERROR_HELP, STATE_LABEL, bytes, isFinal, romLabel } from '../lib/format';
  import { app } from '../lib/state.svelte';
  import type { Job } from '../lib/types';

  let { job, compact = false }: { job: Job; compact?: boolean } = $props();
  let showLog = $state(false);
  let log = $state<string[]>([]);

  const indeterminate = $derived(['queued', 'connecting', 'retrying', 'rebooting'].includes(job.state) && !job.total);
  const pct = $derived(job.state === 'rebooting' || job.state === 'done' ? 100 : job.percent);

  async function toggleLog() {
    showLog = !showLog;
    if (showLog) log = (await api.get<Job>(`/jobs/${job.id}`)).log ?? [];
  }
</script>

<div class="job {job.state}" class:compact>
  <div class="row top">
    <strong class="grow name">{romLabel(job.rom, app.names)}</strong>
    <span class="badge state">{STATE_LABEL[job.state]}{job.state === 'uploading' || job.state === 'decompress' ? ` ${job.percent} %` : ''}</span>
  </div>
  <div class="muted small">
    → {job.cabinet_name} ({job.ip})
    {#if job.source !== 'user'}· {job.source === 'server' ? 'mode serveur' : 'démarrage auto'}{/if}
    {#if job.total && !isFinal(job)}· {bytes(job.done)} / {bytes(job.total)}{/if}
    {#if job.attempts > 1}· essai {job.attempts}{/if}
  </div>
  {#if !isFinal(job)}
    <div class="bar" class:indeterminate><span style="width:{pct}%"></span></div>
  {/if}
  {#if job.state === 'error'}
    <div class="err small">{job.message}{#if job.error_kind && ERROR_HELP[job.error_kind]}<br /><span class="muted">{ERROR_HELP[job.error_kind]}</span>{/if}</div>
  {/if}
  {#if !compact}
    <div class="row actions">
      {#if !isFinal(job)}
        <button class="small danger" onclick={() => app.run(() => api.post(`/jobs/${job.id}/cancel`))}>Annuler</button>
      {:else if job.state !== 'done'}
        <button class="small" onclick={() => app.run(() => api.post(`/jobs/${job.id}/retry`), 'Relancé')}>Relancer</button>
      {/if}
      <button class="small ghost" onclick={toggleLog}>{showLog ? 'Masquer le journal' : 'Journal'}</button>
    </div>
    {#if showLog}<pre>{log.join('\n') || '(vide)'}</pre>{/if}
  {/if}
</div>

<style>
  .job { display: grid; gap: 0.4rem; padding: 0.8rem 0.9rem; border-radius: 12px; background: var(--bg-2); border: 1px solid var(--line); }
  .job.compact { padding: 0.55rem 0.8rem; }
  .name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .done .state { background: color-mix(in srgb, var(--ok) 22%, transparent); color: var(--ok); }
  .error .state { background: color-mix(in srgb, var(--err) 22%, transparent); color: var(--err); }
  .bar { height: 8px; border-radius: 99px; background: var(--bg-3); overflow: hidden; }
  .bar span { display: block; height: 100%; background: var(--accent); transition: width 0.3s; }
  .bar.indeterminate span { width: 35% !important; animation: slide 1.1s infinite ease-in-out; }
  @keyframes slide { from { transform: translateX(-100%); } to { transform: translateX(300%); } }
  .err { color: var(--err); }
  pre { margin: 0; max-height: 240px; overflow: auto; font-size: 0.75rem; background: var(--bg); padding: 0.6rem; border-radius: 8px; white-space: pre-wrap; }
</style>
