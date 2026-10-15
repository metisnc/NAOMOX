<script lang="ts">
  import { api, uploadWithProgress } from '../lib/api';
  import { SYSTEM_SHORT, bytes } from '../lib/format';
  import { app } from '../lib/state.svelte';
  import type { FileEntry, Game, Settings } from '../lib/types';

  type Kind = 'roms' | 'images' | 'videos' | 'firmware';
  const KINDS: { id: Kind; label: string; accept: string }[] = [
    { id: 'roms', label: 'ROMs', accept: '.gz,.bin' },
    { id: 'images', label: 'Images', accept: 'image/*' },
    { id: 'videos', label: 'Vidéos', accept: 'video/mp4,video/webm' },
    { id: 'firmware', label: 'Firmware', accept: '.gz,.bin' },
  ];

  let subnet = $state(app.settings?.cabinet_subnet ?? '');
  let kind = $state<Kind>('roms');
  let files = $state<FileEntry[]>([]);
  let uploading = $state<{ name: string; pct: number } | null>(null);
  let gameFilter = $state('');
  let csvReplace = $state(false);

  async function loadFiles() {
    files = (await app.run(() => api.get<FileEntry[]>(`/files/${kind}`))) ?? [];
  }
  $effect(() => {
    void kind;
    loadFiles();
  });

  async function saveSubnet(e: SubmitEvent) {
    e.preventDefault();
    const s = await app.run(() => api.put<Settings>('/settings', { cabinet_subnet: subnet }), 'Réglage enregistré');
    if (s) app.settings = s;
  }

  async function scan() {
    const r = await app.run(() => api.post<{ present: number; added: string[]; missing: number }>('/games/scan'));
    if (r) {
      app.toast('ok', `${r.present} ROM(s) présente(s), ${r.added.length} nouvelle(s), ${r.missing} référencée(s) sans fichier`, 7000);
      await app.refreshGames();
    }
  }

  async function upload(e: Event) {
    const input = e.target as HTMLInputElement;
    for (const f of Array.from(input.files ?? [])) {
      uploading = { name: f.name, pct: 0 };
      try {
        await uploadWithProgress(`/files/${kind}`, f, (pct) => (uploading = { name: f.name, pct }));
        app.toast('ok', `${f.name} envoyé`);
      } catch (err) {
        app.toast('error', `${f.name} : ${(err as Error).message}`);
      }
    }
    uploading = null;
    input.value = '';
    await loadFiles();
    if (kind !== 'firmware') await app.refreshGames();
  }

  async function removeFile(f: FileEntry) {
    if (!confirm(`Supprimer ${f.name} ?`)) return;
    await app.run(() => api.del(`/files/${kind}/${encodeURIComponent(f.name)}`), 'Fichier supprimé');
    await loadFiles();
    if (kind === 'roms') await app.refreshGames();
  }

  async function importCsv(e: Event) {
    const input = e.target as HTMLInputElement;
    const f = input.files?.[0];
    if (!f) return;
    const form = new FormData();
    form.append('file', f);
    const r = await app.run(() => api.upload<{ imported: number }>(`/games/import?replace=${csvReplace}`, form));
    if (r) app.toast('ok', `${r.imported} jeux importés`);
    input.value = '';
    await app.refreshGames();
  }

  async function patchGame(g: Game, changes: Partial<Game>) {
    const u = await app.run(() => api.patch<Game>(`/games/${encodeURIComponent(g.rom)}`, changes));
    if (u) app.setGame(u);
  }

  async function logout() {
    await api.post('/auth/logout');
    location.reload();
  }

  const gamesList = $derived(
    app.games.filter((g) => g.present && (!gameFilter || g.name.toLowerCase().includes(gameFilter.toLowerCase()))),
  );
</script>

<div class="page">
  <h1>Réglages</h1>

  <h2>Réseau</h2>
  <form class="card stack" onsubmit={saveSubnet}>
    <label class="field">Sous-réseau des bornes (recherche automatique)
      <input bind:value={subnet} placeholder="10.185.10.0/24" />
    </label>
    <div class="row">
      <span class="muted small grow">Port NetDIMM : {app.settings?.netdimm_port}</span>
      <button class="primary small">Enregistrer</button>
    </div>
  </form>

  <h2>Jeux</h2>
  <div class="card stack">
    <div class="row">
      <span class="grow">Détecter les ROMs ajoutées sur le serveur</span>
      <button class="small" onclick={scan}>Scanner</button>
    </div>
    <div class="row">
      <span class="grow">Liste des jeux (format romsinfo.csv de WiPi)</span>
      <a class="btn small" href="/api/v1/games/export.csv" download>Exporter</a>
      <label class="btn small">Importer<input type="file" accept=".csv,text/csv" hidden onchange={importCsv} /></label>
    </div>
    <label class="check small"><input type="checkbox" bind:checked={csvReplace} /> L’import remplace toute la liste</label>
    <details>
      <summary>Activer / désactiver des jeux installés ({gamesList.length})</summary>
      <input type="search" placeholder="Filtrer…" bind:value={gameFilter} />
      <ul class="games">
        {#each gamesList as g (g.rom)}
          <li class="row">
            <label class="check grow"><input type="checkbox" checked={g.enabled} onchange={() => patchGame(g, { enabled: !g.enabled })} />
              <span>{g.name} <span class="muted small">{SYSTEM_SHORT[g.system]}</span></span>
            </label>
          </li>
        {/each}
      </ul>
    </details>
  </div>

  <h2>Fichiers sur le serveur</h2>
  <div class="card stack">
    <div class="tabs">
      {#each KINDS as k (k.id)}
        <button class="small" class:active={kind === k.id} onclick={() => (kind = k.id)}>{k.label}</button>
      {/each}
    </div>
    <label class="btn primary">
      {uploading ? `Envoi de ${uploading.name}… ${uploading.pct} %` : 'Ajouter des fichiers'}
      <input type="file" multiple hidden accept={KINDS.find((k) => k.id === kind)?.accept} onchange={upload} disabled={!!uploading} />
    </label>
    {#if kind === 'firmware'}
      <p class="muted small">Fichiers attendus : FW_Netdimm_401.bin.gz, FW_Netdimm_402.bin.gz, FW_Netdimm_403.bin.gz.</p>
    {/if}
    {#if !files.length}
      <p class="muted">Aucun fichier.</p>
    {:else}
      <ul class="files">
        {#each files as f (f.name)}
          <li class="row">
            <span class="grow name">{f.name}</span>
            <span class="muted small">{bytes(f.size)}</span>
            <button class="small ghost danger" onclick={() => removeFile(f)} aria-label="Supprimer">✕</button>
          </li>
        {/each}
      </ul>
    {/if}
  </div>

  <h2>À propos</h2>
  <div class="card row">
    <span class="grow">NAOMOX {app.settings?.version}</span>
    {#if app.auth?.enabled}<button class="small" onclick={logout}>Se déconnecter</button>{/if}
  </div>
</div>

<style>
  .tabs { display: flex; gap: 0.4rem; flex-wrap: wrap; }
  .tabs .active { background: var(--accent); color: var(--accent-fg); }
  .files, .games { list-style: none; margin: 0; padding: 0; display: grid; gap: 0.2rem; max-height: 50dvh; overflow: auto; }
  .files li { border-bottom: 1px solid var(--line); padding: 0.2rem 0; }
  .name { word-break: break-all; font-size: 0.9rem; }
  details summary { cursor: pointer; min-height: 44px; display: flex; align-items: center; }
  details input[type='search'] { margin: 0.5rem 0; }
</style>
