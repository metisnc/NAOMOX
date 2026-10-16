<script lang="ts">
  // Mise à jour du firmware NetDIMM : volontairement difficile d'accès. Zone repliée,
  // avertissement, lecture de la version actuelle, chemin de mise à jour imposé,
  // engagements à cocher et mot de confirmation à taper. Le serveur revérifie tout.
  import { ApiError, api } from '../lib/api';
  import { app } from '../lib/state.svelte';
  import type { Cabinet, DimmInfo, Job } from '../lib/types';

  let { cabinet, ondone }: { cabinet: Cabinet; ondone: () => void } = $props();

  const WORD = 'FLASHER';
  let step = $state<'closed' | 'warning' | 'form'>('closed');
  let info = $state<DimmInfo | null>(null);
  let infoError = $state<string | null>(null);
  let target = $state<string | null>(null);
  let checks = $state([false, false, false]);
  let typed = $state('');
  let busy = $state(false);
  let error = $state<string | null>(null);

  const current = $derived(info?.firmware ?? null);
  // Mêmes règles que le serveur : pas la même version, pas de retour arrière, 3.x → 4.01 d'abord.
  const allowed = $derived.by(() => {
    const all = app.systems?.firmware_versions ?? [];
    if (!current || current === 'UNKNOWN') return all;
    if (/^[123]\./.test(current)) return all.filter((v) => v === '4.01');
    return all.filter((v) => v > current);
  });
  const ready = $derived(!!target && checks.every(Boolean) && typed.trim().toUpperCase() === WORD && !busy);

  async function readInfo() {
    step = 'form';
    info = null;
    infoError = null;
    try {
      info = await api.get<DimmInfo>(`/cabinets/${cabinet.id}/info`);
      target = allowed[0] ?? null;
    } catch (e) {
      infoError = (e as Error).message;
    }
  }

  async function flash() {
    if (!target) return;
    busy = true;
    error = null;
    try {
      const job = await api.post<Job>(`/cabinets/${cabinet.id}/firmware`, { version: target, confirm: true });
      app.jobs[job.id] = job;
      app.toast('info', 'Firmware envoyé : suivez les instructions à l’écran de la borne. NE PAS L’ÉTEINDRE.', 12000);
      step = 'closed';
      ondone();
    } catch (e) {
      error = e instanceof ApiError ? e.message : (e as Error).message;
    } finally {
      busy = false;
    }
  }

  function close() {
    step = 'closed';
    checks = [false, false, false];
    typed = '';
    error = null;
  }
</script>

<details class="danger-zone" ontoggle={(e) => !(e.currentTarget as HTMLDetailsElement).open && close()}>
  <summary>⚠ Zone avancée : firmware de la NetDIMM</summary>

  {#if step === 'closed'}
    <div class="warn-box">
      <strong>Opération à risque.</strong>
      <p>
        Flasher le firmware réécrit la mémoire de la NetDIMM. Une coupure de courant ou de réseau, un mauvais
        fichier ou une carte non compatible peuvent la rendre <b>définitivement inutilisable</b> (récupération
        uniquement par un spécialiste). Ne le faites que si un jeu l’exige ou sur conseil.
      </p>
      <ul>
        <li>NetDIMM <b>type 1</b> uniquement, firmware actuel 3.03 ou plus.</li>
        <li>Depuis une version 3.x, passer d’abord en <b>4.01</b>.</li>
        <li>La borne doit rester allumée et branchée pendant toute l’opération et suivre les instructions à l’écran.</li>
      </ul>
      <button class="danger" onclick={() => (step = 'warning')}>Je comprends les risques, continuer</button>
    </div>
  {:else if step === 'warning'}
    <div class="warn-box">
      <p>NAOMOX va d’abord lire la version installée sur <b>{cabinet.name}</b> ({cabinet.ip}).</p>
      <div class="row">
        <button onclick={close}>Annuler</button>
        <button class="danger" onclick={readInfo}>Lire la version actuelle</button>
      </div>
    </div>
  {:else}
    <div class="warn-box">
      {#if infoError}
        <p class="err">{infoError}</p>
        <p class="small">La mise à jour est impossible sans pouvoir lire la version actuelle.</p>
        <button onclick={close}>Fermer</button>
      {:else if !info}
        <p class="muted">Lecture de la NetDIMM…</p>
      {:else if !allowed.length}
        <p>Firmware actuel : <b>{current}</b>. Aucune mise à jour disponible (déjà à jour).</p>
        <button onclick={close}>Fermer</button>
      {:else}
        <p>Firmware actuel : <b>{current}</b></p>
        <label class="field">Nouvelle version
          <select bind:value={target}>
            {#each allowed as v (v)}<option value={v}>{v}</option>{/each}
          </select>
        </label>
        <label class="check small"><input type="checkbox" bind:checked={checks[0]} /> La borne est sur une alimentation stable et ne sera pas éteinte.</label>
        <label class="check small"><input type="checkbox" bind:checked={checks[1]} /> Je surveille l’écran de la borne et je suis ses instructions jusqu’au bout.</label>
        <label class="check small"><input type="checkbox" bind:checked={checks[2]} /> J’accepte qu’un échec puisse rendre la NetDIMM inutilisable.</label>
        <label class="field"><span>Tapez <b>{WORD}</b> pour confirmer</span>
          <input bind:value={typed} autocomplete="off" autocapitalize="characters" spellcheck="false" />
        </label>
        {#if error}<p class="err">{error}</p>{/if}
        <div class="row">
          <button onclick={close}>Annuler</button>
          <button class="danger solid" disabled={!ready} onclick={flash}>Flasher en {target}</button>
        </div>
      {/if}
    </div>
  {/if}
</details>

<style>
  .danger-zone { border: 1px solid color-mix(in srgb, var(--err) 45%, var(--line)); border-radius: 12px; padding: 0 0.8rem; }
  summary { cursor: pointer; min-height: 44px; display: flex; align-items: center; font-weight: 700; color: var(--err); }
  .warn-box { display: grid; gap: 0.6rem; padding: 0 0 0.9rem; }
  .warn-box p, .warn-box ul { margin: 0; font-size: 0.88rem; }
  .warn-box ul { padding-left: 1.1rem; color: var(--fg-2); }
  .err { color: var(--err); }
  button.danger.solid { background: var(--err); color: #fff; border-color: transparent; font-weight: 700; }
  button.danger.solid:disabled { background: var(--bg-3); color: var(--fg-2); }
</style>
