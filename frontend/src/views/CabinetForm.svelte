<script lang="ts">
  import Sheet from '../components/Sheet.svelte';
  import { api } from '../lib/api';
  import { SYSTEM_SHORT } from '../lib/format';
  import { app } from '../lib/state.svelte';
  import type { Cabinet, CabinetFields, Job } from '../lib/types';

  let {
    open = $bindable(false),
    cabinet = null,
    prefillIp = '',
  }: { open: boolean; cabinet: Cabinet | null; prefillIp?: string } = $props();

  const blank = (): CabinetFields => ({
    name: '',
    ip: '',
    type: 'Sega Naomi',
    enabled: true,
    default_game: null,
    time_hack: false,
    server_mode: false,
    osm_theme: 'dark',
    osm_mode: 'once',
  });

  // « 10,185,10,5 » ou « 10.185.10.5 » avec espaces → « 10.185.10.5 ».
  const normalizeIp = (v: string) => v.trim().replace(/[,;\s]+/g, '.').replace(/\.{2,}/g, '.');

  let form = $state<CabinetFields>(blank());
  let busy = $state(false);
  let fwVersion = $state('4.03');
  let fwConfirm = $state(false);

  $effect(() => {
    if (open) {
      form = cabinet ? { ...$state.snapshot(cabinet) } : { ...blank(), ip: prefillIp };
      fwConfirm = false;
    }
  });

  const compatibleGames = $derived.by(() => {
    const systems = app.systems?.compatibility[form.type] ?? [];
    return app.games.filter((g) => g.present && systems.includes(g.system)).sort((a, b) => a.name.localeCompare(b.name));
  });

  async function save(e: SubmitEvent) {
    e.preventDefault();
    busy = true;
    form.ip = normalizeIp(form.ip);
    const body = { ...form, default_game: form.default_game || null };
    const ok = cabinet
      ? await app.run(() => api.patch(`/cabinets/${cabinet.id}`, body), 'Borne mise à jour')
      : await app.run(() => api.post('/cabinets', body), 'Borne ajoutée');
    busy = false;
    if (ok) {
      open = false;
      await app.refreshCabinets();
    }
  }

  async function remove() {
    if (!cabinet || !confirm(`Supprimer la borne ${cabinet.name} ?`)) return;
    const ok = await app.run(() => api.del(`/cabinets/${cabinet.id}`).then(() => true), 'Borne supprimée');
    if (ok) {
      open = false;
      await app.refreshCabinets();
    }
  }

  async function firmware() {
    if (!cabinet) return;
    const job = await app.run(() => api.post<Job>(`/cabinets/${cabinet.id}/firmware`, { version: fwVersion, confirm: fwConfirm }));
    if (job) {
      app.jobs[job.id] = job;
      app.toast('info', 'Firmware envoyé : suivez les instructions à l’écran de la borne.', 8000);
      open = false;
    }
  }

  async function diag() {
    if (!cabinet) return;
    const job = await app.run(() => api.post<Job>(`/cabinets/${cabinet.id}/diag`));
    if (job) {
      app.jobs[job.id] = job;
      open = false;
    }
  }
</script>

<Sheet bind:open title={cabinet ? `Modifier ${cabinet.name}` : 'Nouvelle borne'}>
  <form class="stack" onsubmit={save}>
    <label class="field">Nom<input required maxlength="64" bind:value={form.name} placeholder="Naomi salon" /></label>
    <label class="field">Adresse IP de la NetDIMM
      <!-- Clavier texte : le clavier « décimal » des téléphones en français n'a pas de point. -->
      <input
        required
        type="text"
        autocomplete="off"
        autocapitalize="off"
        spellcheck="false"
        bind:value={form.ip}
        onblur={() => (form.ip = normalizeIp(form.ip))}
        placeholder="10.185.10.50"
      />
    </label>
    <label class="field">Type de borne
      <select bind:value={form.type}>
        {#each app.systems?.dimm_types ?? [] as t (t)}<option value={t}>{SYSTEM_SHORT[t] ?? t}</option>{/each}
      </select>
    </label>
    <label class="field">Au démarrage de la borne
      <select bind:value={form.default_game}>
        <option value={null}>Ne rien envoyer</option>
        {#each compatibleGames as g (g.rom)}<option value={g.rom}>{g.name}</option>{/each}
      </select>
    </label>
    <label class="check"><input type="checkbox" bind:checked={form.server_mode} />
      <span>Mode serveur <span class="muted small">— renvoie le dernier jeu à chaque mise sous tension</span></span>
    </label>
    <label class="check"><input type="checkbox" bind:checked={form.time_hack} />
      <span>Time hack <span class="muted small">— pour démarrer sans zero-key PIC</span></span>
    </label>
    <label class="check"><input type="checkbox" bind:checked={form.enabled} /><span>Borne active</span></label>
    <div class="row">
      {#if cabinet}<button type="button" class="danger" onclick={remove}>Supprimer</button>{/if}
      <span class="grow"></span>
      <button type="button" onclick={() => (open = false)}>Annuler</button>
      <button class="primary" disabled={busy}>Enregistrer</button>
    </div>
  </form>

  {#if cabinet}
    <h2>Maintenance</h2>
    <div class="stack card">
      {#if cabinet.type === 'Sega Naomi' || cabinet.type === 'Sega Naomi2'}
        <div class="row">
          <span class="grow">Diagnostic Naomi (homebrew)</span>
          <button class="small" onclick={diag}>Lancer</button>
        </div>
      {/if}
      <div class="stack">
        <span>Mise à jour du firmware NetDIMM</span>
        <div class="row">
          <select bind:value={fwVersion} class="grow">
            {#each app.systems?.firmware_versions ?? [] as v (v)}<option value={v}>{v}</option>{/each}
          </select>
          <button class="small danger" disabled={!fwConfirm} onclick={firmware}>Envoyer</button>
        </div>
        <label class="check small"><input type="checkbox" bind:checked={fwConfirm} />
          Je confirme : la borne va flasher la NetDIMM, ne pas l’éteindre pendant l’opération.
        </label>
      </div>
    </div>
  {/if}
</Sheet>
