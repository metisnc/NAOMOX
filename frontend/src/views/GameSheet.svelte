<script lang="ts">
  import Sheet from '../components/Sheet.svelte';
  import { ApiError, api } from '../lib/api';
  import { SYSTEM_SHORT } from '../lib/format';
  import { app } from '../lib/state.svelte';
  import type { CabinetChoice, Game, Job } from '../lib/types';

  let { open = $bindable(false), rom }: { open: boolean; rom: string } = $props();

  const game = $derived(app.games.find((g) => g.rom === rom));
  let choices = $state<CabinetChoice[] | null>(null);
  let note = $state<string | null>(null);
  let busy = $state(false);

  // Bornes compatibles (pour le choix explicite).
  const compatible = $derived.by(() => {
    const g = game;
    const table = app.systems?.compatibility ?? {};
    return g ? app.cabinets.filter((c) => c.enabled && (table[c.type] ?? []).includes(g.system)) : [];
  });

  $effect(() => {
    if (open) {
      choices = null;
      note = null;
    }
  });

  async function launch(cabinetId?: string) {
    if (!game) return;
    busy = true;
    note = null;
    try {
      const job = await api.post<Job>('/launch', { rom: game.rom, cabinet_id: cabinetId });
      app.jobs[job.id] = job;
      app.toast('info', `Envoi vers ${job.cabinet_name}…`);
      open = false;
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        choices = (e.detail.choices as CabinetChoice[]) ?? [];
        note = e.message;
      } else {
        note = (e as Error).message;
      }
    } finally {
      busy = false;
    }
  }

  async function toggleFav(g: Game) {
    const u = await app.run(() => api.patch<Game>(`/games/${encodeURIComponent(g.rom)}`, { favourite: !g.favourite }));
    if (u) app.setGame(u);
  }
</script>

<Sheet bind:open title={game?.name ?? ''}>
  {#if game}
    <div class="stack">
      {#if game.video}
        <!-- svelte-ignore a11y_media_has_caption -->
        <video src={game.video} poster={game.image ?? undefined} autoplay muted loop playsinline></video>
      {:else if game.image}
        <img src={game.image} alt="" />
      {/if}
      <div class="row">
        <span class="badge">{SYSTEM_SHORT[game.system] ?? game.system}</span>
        {#if game.year}<span class="badge">{game.year}</span>{/if}
        {#if game.manufacturer}<span class="badge">{game.manufacturer}</span>{/if}
        {#if game.genre}<span class="badge">{game.genre}</span>{/if}
        {#if game.orientation}<span class="badge">{game.orientation}</span>{/if}
        <span class="grow"></span>
        <button class="small ghost fav" class:on={game.favourite} onclick={() => toggleFav(game)} aria-label="Favori">
          {game.favourite ? '★' : '☆'}
        </button>
      </div>
      {#if game.controls}<p class="muted small">Commandes : {game.controls}</p>{/if}
      <p class="muted small mono">{game.rom}</p>

      {#if !game.present}
        <p class="warn">ROM absente du serveur : impossible de lancer ce jeu.</p>
      {:else if !game.enabled}
        <p class="warn">Jeu désactivé (activable dans Réglages).</p>
      {:else if !compatible.length}
        <p class="warn">Aucune borne compatible {SYSTEM_SHORT[game.system]} n’est configurée. <a href="#/bornes" onclick={() => (open = false)}>Ajouter une borne</a></p>
      {:else}
        <button class="primary launch" disabled={busy} onclick={() => launch()}>▶ Lancer</button>
        {#if note}<p class="warn">{note}</p>{/if}
        {#if choices !== null || compatible.length > 1}
          <div class="stack">
            <span class="muted small">Choisir la borne :</span>
            {#each choices ?? compatible.map((c) => ({ id: c.id, name: c.name, ip: c.ip, type: c.type, online: !!c.status.online })) as c (c.id)}
              <button class="choice" disabled={busy} onclick={() => launch(c.id)}>
                <span class="dot" class:on={c.online} class:off={!c.online}></span>
                <span class="grow">{c.name}</span>
                <span class="muted small">{c.ip}</span>
              </button>
            {/each}
          </div>
        {/if}
      {/if}
    </div>
  {/if}
</Sheet>

<style>
  video, img { width: 100%; border-radius: 12px; background: #000; max-height: 42dvh; object-fit: contain; }
  .launch { font-size: 1.15rem; min-height: 56px; }
  .warn { color: var(--warn); margin: 0; }
  .fav { font-size: 1.4rem; color: var(--fg-2); }
  .fav.on { color: var(--accent); }
  .mono { font-family: ui-monospace, monospace; word-break: break-all; }
  .choice { justify-content: flex-start; gap: 0.7rem; }
</style>
