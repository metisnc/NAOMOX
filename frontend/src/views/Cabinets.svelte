<script lang="ts">
  import JobCard from '../components/JobCard.svelte';
  import Sheet from '../components/Sheet.svelte';
  import { api } from '../lib/api';
  import { SYSTEM_SHORT, ago, bytes, romLabel } from '../lib/format';
  import { app } from '../lib/state.svelte';
  import type { Cabinet, DimmInfo } from '../lib/types';
  import CabinetForm from './CabinetForm.svelte';

  let editing = $state<Cabinet | null>(null);
  let formOpen = $state(false);
  let prefillIp = $state('');

  let infoOpen = $state(false);
  let infoCab = $state<Cabinet | null>(null);
  let info = $state<DimmInfo | null>(null);
  let infoError = $state<string | null>(null);

  let discoverOpen = $state(false);
  let scanning = $state(false);
  let found = $state<{ ip: string; cabinet_id: string | null }[] | null>(null);

  function add(ip = '') {
    editing = null;
    prefillIp = ip;
    formOpen = true;
    discoverOpen = false;
  }

  function edit(c: Cabinet) {
    editing = c;
    formOpen = true;
  }

  async function showInfo(c: Cabinet) {
    infoCab = c;
    info = null;
    infoError = null;
    infoOpen = true;
    try {
      info = await api.get<DimmInfo>(`/cabinets/${c.id}/info`);
    } catch (e) {
      infoError = (e as Error).message;
    }
  }

  async function reboot(c: Cabinet) {
    if (!confirm(`Redémarrer ${c.name} ?`)) return;
    await app.run(() => api.post(`/cabinets/${c.id}/reboot`), 'Redémarrage demandé');
  }

  async function discover() {
    discoverOpen = true;
    scanning = true;
    found = null;
    const r = await app.run(() => api.post<{ subnet: string; found: { ip: string; cabinet_id: string | null }[] }>('/cabinets/discover'));
    found = r?.found ?? [];
    scanning = false;
  }

  const supported = (type: string) => (app.systems?.compatibility[type] ?? []).map((s) => SYSTEM_SHORT[s] ?? s).join(', ');
</script>

<div class="page">
  <div class="row head">
    <h1 class="grow">Bornes</h1>
    <button onclick={discover}>Rechercher</button>
    <button class="primary" onclick={() => add()}>+ Ajouter</button>
  </div>

  {#if !app.cabinets.length}
    <div class="empty">
      <p>Aucune borne configurée.</p>
      <p class="small">Ajoutez l’adresse IP de chaque NetDIMM (réglée dans le menu test de la borne), ou lancez une recherche sur le réseau.</p>
    </div>
  {/if}

  <div class="list">
    {#each app.cabinets as c (c.id)}
      <article class="card cab" class:disabled={!c.enabled}>
        <div class="row">
          <span class="dot" class:on={c.status.online === true} class:off={c.status.online === false}></span>
          <h3 class="grow">{c.name}</h3>
          <span class="badge">{SYSTEM_SHORT[c.type] ?? c.type}</span>
        </div>
        <div class="muted small">
          {c.ip} ·
          {c.status.online === null ? 'état inconnu' : c.status.online ? 'en ligne' : 'hors ligne'}
          {#if c.status.since}({ago(c.status.since)}){/if}
          {#if !c.enabled}· désactivée{/if}
        </div>
        <div class="small">
          Jeu : <strong>{romLabel(c.status.game, app.names)}</strong>
          {#if c.status.launched_at}<span class="muted">· {ago(c.status.launched_at)}</span>{/if}
        </div>
        <div class="row tags">
          {#if c.server_mode}<span class="badge">mode serveur</span>{/if}
          {#if c.time_hack}
            <span class="badge" class:bad={c.status.time_hack.ok === false}>
              time hack{c.status.time_hack.ok === false ? ' en échec' : ''}
            </span>
          {/if}
          {#if c.default_game}<span class="badge">auto : {c.default_game === 'menu' ? 'menu' : romLabel(c.default_game, app.names)}</span>{/if}
        </div>
        {#if c.status.current_job}<JobCard job={c.status.current_job} compact />{/if}
        <div class="row actions">
          <button class="small" onclick={() => showInfo(c)}>Infos</button>
          <button class="small" onclick={() => reboot(c)} disabled={c.status.busy}>Redémarrer</button>
          <span class="grow"></span>
          <button class="small" onclick={() => edit(c)}>Modifier</button>
        </div>
      </article>
    {/each}
  </div>
</div>

<CabinetForm bind:open={formOpen} cabinet={editing} {prefillIp} />

<Sheet bind:open={infoOpen} title={`NetDIMM — ${infoCab?.name ?? ''}`}>
  {#if infoError}
    <p class="err">{infoError}</p>
  {:else if !info}
    <p class="muted">Interrogation de la NetDIMM…</p>
  {:else}
    <dl>
      <dt>Firmware</dt><dd>{info.firmware}</dd>
      <dt>Mémoire DIMM</dt><dd>{info.memory_mb} Mo</dd>
      <dt>Mémoire jeu</dt><dd>{bytes(info.game_memory_bytes)}</dd>
      <dt>Jeu chargé</dt><dd>{info.current_game_size ? bytes(info.current_game_size) : 'aucun'}</dd>
      <dt>CRC</dt><dd>{info.current_game_crc} ({info.crc_status})</dd>
      <dt>Types acceptés</dt><dd>{infoCab ? supported(infoCab.type) : ''}</dd>
    </dl>
  {/if}
</Sheet>

<Sheet bind:open={discoverOpen} title="Recherche de NetDIMM">
  {#if scanning}
    <p class="muted">Balayage de {app.settings?.cabinet_subnet} (port {app.settings?.netdimm_port})…</p>
  {:else if found && !found.length}
    <p>Aucune NetDIMM trouvée sur {app.settings?.cabinet_subnet}.</p>
    <p class="muted small">Borne allumée ? IP dans ce sous-réseau ? Le sous-réseau se règle dans Réglages.</p>
  {:else if found}
    <div class="stack">
      {#each found as f (f.ip)}
        <div class="row">
          <span class="grow">{f.ip}</span>
          {#if f.cabinet_id}
            <span class="muted small">{app.cabinets.find((c) => c.id === f.cabinet_id)?.name}</span>
          {:else}
            <button class="small primary" onclick={() => add(f.ip)}>Ajouter</button>
          {/if}
        </div>
      {/each}
    </div>
  {/if}
</Sheet>

<style>
  .head { margin-bottom: 1rem; }
  .list { display: grid; gap: 0.8rem; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); }
  .cab { display: grid; gap: 0.5rem; }
  .cab.disabled { opacity: 0.6; }
  .tags:empty { display: none; }
  .badge.bad { color: var(--err); }
  .err { color: var(--err); }
  dl { display: grid; grid-template-columns: auto 1fr; gap: 0.4rem 1rem; margin: 0; }
  dt { color: var(--fg-2); }
  dd { margin: 0; }
</style>
