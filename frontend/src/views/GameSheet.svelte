<script lang="ts">
  import { untrack } from 'svelte';
  import GameTile from '../components/GameTile.svelte';
  import ProgressBar from '../components/ProgressBar.svelte';
  import Marquee from '../components/Marquee.svelte';
  import Sheet from '../components/Sheet.svelte';
  import { ApiError, api } from '../lib/api';
  import {
    controlsLabel,
    genreIcon,
    genreLabel,
    orientationLabel,
    publisher,
    ratingInfo,
    sameGenre,
    systemColor,
    systemShort,
    variants,
    displayName,
  } from '../lib/catalog';
  import { ERROR_HELP, ago, romLabel } from '../lib/format';
  import { jobMessage, jobPercent, jobTone } from '../lib/progress';
  import { app } from '../lib/state.svelte';
  import type { Cabinet, Game, Job } from '../lib/types';

  let { open = $bindable(false), rom = $bindable() }: { open: boolean; rom: string } = $props();

  const LAST_CAB = 'naomox.last-cabinet';
  const game = $derived(app.games.find((g) => g.rom === rom));
  let sheet = $state<ReturnType<typeof Sheet> | null>(null);
  let chosen = $state<string | null>(null);
  let jobId = $state<string | null>(null);
  let note = $state<string | null>(null);
  let busy = $state(false);
  let muted = $state(true);
  let videoOk = $state(true);
  // Vidéo : le logo se range en haut à gauche pendant la lecture, revient au centre en pause.
  let video = $state<HTMLVideoElement | null>(null);
  let playing = $state(false);
  let docked = $state(false);
  let dockTimer: ReturnType<typeof setTimeout> | null = null;

  function onPlay() {
    playing = true;
    if (dockTimer) clearTimeout(dockTimer);
    // Laisser le logo visible au centre un instant avant qu'il ne se range.
    dockTimer = setTimeout(() => (docked = true), 1200);
  }
  function onPause() {
    playing = false;
    if (dockTimer) clearTimeout(dockTimer);
    docked = false;
  }
  function togglePlay() {
    if (!video) return;
    if (video.paused) video.play().catch(() => {});
    else video.pause();
  }
  let showLog = $state(false);
  let log = $state<string[]>([]);

  async function toggleLog() {
    showLog = !showLog;
    if (showLog && jobId) log = (await api.get<Job>(`/jobs/${jobId}`)).log ?? [];
  }

  const job = $derived<Job | undefined>(jobId ? app.jobs[jobId] : undefined);
  const rating = $derived(game ? ratingInfo(game.rating) : null);
  const similar = $derived(game ? sameGenre(app.games, game) : []);

  const compatible = $derived.by<Cabinet[]>(() => {
    const g = game;
    const table = app.systems?.compatibility ?? {};
    return g ? app.cabinets.filter((c) => c.enabled && (table[c.type] ?? []).includes(g.system)) : [];
  });

  // Au changement de jeu : réinitialiser et présélectionner la borne la plus probable.
  $effect(() => {
    void rom;
    untrack(() => preselect());
  });

  function preselect() {
    onPause();
    jobId = null;
    showLog = false;
    note = null;
    videoOk = true;
    let last: string | null = null;
    try {
      last = localStorage.getItem(LAST_CAB);
    } catch {
      last = null;
    }
    const online = compatible.filter((c) => c.status.online);
    chosen = (online.find((c) => c.id === last) ?? online[0] ?? compatible.find((c) => c.id === last) ?? compatible[0])?.id ?? null;
    sheet?.scrollTop();
  }

  const target = $derived(compatible.find((c) => c.id === chosen));

  async function launch() {
    if (!game || !target) return;
    busy = true;
    note = null;
    try {
      const j = await api.post<Job>('/launch', { rom: game.rom, cabinet_id: target.id });
      app.jobs[j.id] = j;
      jobId = j.id;
      try {
        localStorage.setItem(LAST_CAB, target.id);
      } catch {
        /* stockage indisponible */
      }
    } catch (e) {
      note = e instanceof ApiError ? e.message : (e as Error).message;
    } finally {
      busy = false;
    }
  }

  async function toggleFav(g: Game) {
    const u = await app.run(() => api.patch<Game>(`/games/${encodeURIComponent(g.rom)}`, { favourite: !g.favourite }));
    if (u) app.setGame(u);
  }

  const done = $derived(job?.state === 'done');
  const running = $derived(job && !['done', 'error', 'cancelled'].includes(job.state));
</script>

<Sheet bind:this={sheet} bind:open title={game?.name ?? ''} wide bare>
  {#if game}
    <article class="fiche" style="--sys:{systemColor(game.system)}">
      <header class="hero" class:playing={docked} class:has-video={game.video && videoOk}>
        {#if game.video && videoOk}
          <!-- svelte-ignore a11y_media_has_caption -->
          <video
            bind:this={video}
            src={game.video}
            autoplay
            loop
            playsinline
            {muted}
            onplay={onPlay}
            onpause={onPause}
            onerror={() => ((videoOk = false), onPause())}
          ></video>
          <button class="tap" onclick={togglePlay} aria-label={playing ? 'Mettre la vidéo en pause' : 'Lire la vidéo'}></button>
          <div class="vctl">
            <button onclick={togglePlay} aria-label={playing ? 'Pause' : 'Lecture'}>{playing ? '❚❚' : '▶'}</button>
            <button onclick={() => (muted = !muted)} aria-label={muted ? 'Activer le son' : 'Couper le son'}>{muted ? '🔇' : '🔊'}</button>
          </div>
        {/if}
        <div class="glow"></div>
        <div class="logo"><Marquee image={game.image} name={displayName(game)} system={game.system} size="lg" /></div>
      </header>

      <div class="content">
        <div class="main">
          <div class="titlebar">
            <div class="grow">
              <h2>{displayName(game)}{#each variants(game) as v (v)}<span class="variant">{v}</span>{/each}</h2>
              <p class="sub">{game.manufacturer || 'Éditeur inconnu'}{game.year ? ` · ${game.year}` : ''}</p>
            </div>
            <button class="fav" class:on={game.favourite} onclick={() => toggleFav(game)} aria-label={game.favourite ? 'Retirer des favoris' : 'Ajouter aux favoris'}>
              {game.favourite ? '★' : '☆'}
            </button>
          </div>

          <div class="tags">
            <span class="tag sys"><i></i>{systemShort(game.system)}</span>
            {#if game.genre}<span class="tag">{genreIcon(game.genre)} {genreLabel(game.genre)}</span>{/if}
            {#if rating}<span class="tag" style="--c:{rating.color}"><i class="r"></i>{rating.label}</span>{/if}
          </div>

          <dl class="facts">
            <div><dt>Commandes</dt><dd>{controlsLabel(game.controls)}</dd></div>
            <div><dt>Écran</dt><dd>{orientationLabel(game.orientation)}</dd></div>
            <div><dt>Éditeur</dt><dd>{publisher(game.manufacturer)}</dd></div>
            <div><dt>Parties lancées</dt><dd>{game.plays || 'jamais'}{game.last_played ? ` · ${ago(game.last_played)}` : ''}</dd></div>
          </dl>
        </div>

        <aside class="launch">
          {#if !game.present}
            <p class="warn">ROM absente du serveur : ajoutez <span class="mono">{game.rom}</span> dans Réglages → Fichiers.</p>
          {:else if !game.enabled}
            <p class="warn">Jeu désactivé (Réglages → Jeux).</p>
          {:else if !compatible.length}
            <p class="warn">Aucune borne {systemShort(game.system)} configurée. <a href="#/bornes" onclick={() => (open = false)}>Ajouter une borne</a></p>
          {:else if job && (running || done || job.state === 'error' || job.state === 'cancelled')}
            <!-- Écran de lancement façon WiPiNetbooter-NG -->
            <div class="launching">
              <div class="lp-logo"><Marquee image={game.image} name={displayName(game)} system={game.system} size="lg" /></div>
              <h3>{displayName(game)}</h3>
              <p class="lp-to">→ {job.cabinet_name}</p>
              <p class="launch-msg {jobTone(job)}">{jobMessage(job)}</p>
              {#if running}<ProgressBar value={jobPercent(job)} />{/if}
              {#if job.state === 'error' && job.error_kind && ERROR_HELP[job.error_kind]}
                <p class="hint">{ERROR_HELP[job.error_kind]}</p>
              {/if}
              <div class="pills">
                {#if running}
                  <button class="pill" onclick={() => app.run(() => api.post(`/jobs/${job.id}/cancel`))}>Annuler</button>
                {:else if done}
                  <button class="pill primary" onclick={() => (open = false)}>Fermer</button>
                {:else}
                  <button class="pill primary" onclick={launch}>Réessayer</button>
                  <button class="pill" onclick={() => (jobId = null)}>Autre borne</button>
                {/if}
                <button class="pill ghost" onclick={toggleLog}>{showLog ? 'Masquer le journal' : 'Journal'}</button>
              </div>
              {#if showLog}<pre class="launch-log">{log.join('\n') || '(vide)'}</pre>{/if}
            </div>
          {:else}
            <h4>Lancer sur</h4>
            <div class="cabs" role="radiogroup" aria-label="Borne">
              {#each compatible as c (c.id)}
                <button
                  class="cab"
                  class:sel={chosen === c.id}
                  role="radio"
                  aria-checked={chosen === c.id}
                  onclick={() => (chosen = c.id)}
                >
                  <span class="dot" class:on={c.status.online === true} class:off={c.status.online === false}></span>
                  <span class="cn">
                    <strong>{c.name}</strong>
                    <small>
                      {c.status.online === false ? 'hors ligne' : c.status.busy ? 'transfert en cours' : c.status.game ? `joue à ${romLabel(c.status.game, app.names)}` : 'en ligne'}
                    </small>
                  </span>
                </button>
              {/each}
            </div>
            <button class="launch-btn" disabled={busy || !target} onclick={launch}>▶&nbsp; Lancer</button>
            {#if target}<p class="lp-on">sur <strong>{target.name}</strong></p>{/if}
            {#if target && target.status.online === false}
              <p class="hint">La borne semble éteinte : NAOMOX réessaiera quelques secondes avant d’abandonner.</p>
            {/if}
            {#if target?.status.busy}<p class="hint">Un transfert est en cours : ce lancement passera ensuite.</p>{/if}
            {#if note}<p class="warn">{note}</p>{/if}
          {/if}
        </aside>
      </div>

      {#if similar.length}
        <section class="similar">
          <h4>Dans le même genre</h4>
          <div class="row">
            {#each similar as g (g.rom)}
              <div class="cell"><GameTile game={g} onopen={(x) => (rom = x.rom)} /></div>
            {/each}
          </div>
        </section>
      {/if}
    </article>
  {/if}
</Sheet>

<style>
  .fiche { --r: 22px; }
  .hero {
    position: relative; display: grid; place-items: center; overflow: hidden;
    width: 100%; height: min(56.25vw, 46dvh, 560px); min-height: 210px; border-radius: var(--r) var(--r) 0 0;
    background: radial-gradient(120% 120% at 50% 10%, color-mix(in srgb, var(--sys) 45%, #000), #040507 75%);
  }
  .hero video { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; opacity: 0.45; transition: opacity 0.7s; }
  .hero.playing video { opacity: 0.95; }
  .glow { position: absolute; inset: 0; pointer-events: none; background: linear-gradient(180deg, rgb(0 0 0 / 0.15) 0%, transparent 35%, rgb(0 0 0 / 0.55) 75%, var(--bg-2) 100%); transition: opacity 0.7s; }
  .hero.playing .glow { opacity: 0.55; }
  /* Logo : centré et grand à l'arrêt, petit en haut à gauche pendant la lecture. */
  .logo {
    position: absolute; z-index: 1; left: 50%; top: 50%; width: min(78%, 460px);
    transform: translate(-50%, -50%); pointer-events: none;
    transition: left 0.7s cubic-bezier(0.65, 0, 0.25, 1), top 0.7s cubic-bezier(0.65, 0, 0.25, 1),
      width 0.7s cubic-bezier(0.65, 0, 0.25, 1), transform 0.7s cubic-bezier(0.65, 0, 0.25, 1);
  }
  .hero.playing .logo { left: 16px; top: 16px; width: min(34%, 210px); transform: translate(0, 0); }
  .hero.playing .logo :global(img) { max-height: 80px; }
  .tap { position: absolute; inset: 0; z-index: 0; border: 0; border-radius: 0; background: transparent; min-height: 0; }
  .vctl { position: absolute; right: 12px; bottom: 26px; z-index: 2; display: flex; gap: 0.4rem; }
  .vctl button {
    width: 40px; min-height: 40px; padding: 0; border-radius: 50%; font-size: 0.95rem; color: #fff;
    background: rgb(0 0 0 / 0.55); border-color: rgb(255 255 255 / 0.25); backdrop-filter: blur(6px);
  }

  .content { display: grid; gap: 1.2rem; padding: 0.4rem 1rem 0; }
  @media (min-width: 760px) { .content { grid-template-columns: 1fr 320px; align-items: start; } }

  .titlebar { display: flex; align-items: flex-start; gap: 0.6rem; }
  h2 { margin: 0; font-size: 1.45rem; line-height: 1.15; color: var(--fg); }
  .variant { display: inline-block; margin-left: 0.4rem; vertical-align: middle; font-size: 0.72rem; font-weight: 700; padding: 0.1rem 0.5rem; border-radius: 99px; background: var(--bg-3); color: var(--fg-2); }
  .sub { margin: 0.25rem 0 0; color: var(--fg-2); }
  .fav { width: 46px; min-height: 46px; padding: 0; border-radius: 50%; font-size: 1.4rem; color: var(--fg-2); }
  .fav.on { color: var(--neon-gold); border-color: color-mix(in srgb, var(--neon-gold) 50%, var(--line)); background: color-mix(in srgb, var(--neon-gold) 14%, var(--bg-3)); }

  .tags { display: flex; flex-wrap: wrap; gap: 0.4rem; margin: 0.8rem 0; }
  .tag { display: inline-flex; align-items: center; gap: 0.35rem; padding: 0.25rem 0.7rem; border-radius: 99px; background: var(--bg-3); font-size: 0.85rem; }
  .tag.sys { background: color-mix(in srgb, var(--sys) 22%, var(--bg-3)); font-weight: 700; }
  .tag i { width: 9px; height: 9px; border-radius: 50%; background: var(--sys); box-shadow: 0 0 8px var(--sys); }
  .tag i.r { background: var(--c); box-shadow: none; }

  .facts { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0.5rem; margin: 0; }
  @media (min-width: 560px) { .facts { grid-template-columns: repeat(4, minmax(0, 1fr)); } }
  .facts div { background: var(--bg); border: 1px solid var(--line); border-radius: 12px; padding: 0.55rem 0.7rem; min-width: 0; }
  dt { font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.06em; color: var(--fg-2); }
  dd { margin: 0.15rem 0 0; font-weight: 600; font-size: 0.92rem; overflow: hidden; text-overflow: ellipsis; }
  .mono { font-family: ui-monospace, monospace; word-break: break-all; }

  .launch { display: grid; gap: 0.6rem; background: var(--bg); border: 1px solid var(--line); border-radius: 16px; padding: 0.9rem; }
  @media (min-width: 760px) { .launch { position: sticky; top: 1rem; } }
  h4 { margin: 0; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.08em; color: var(--fg-2); }
  .cabs { display: grid; gap: 0.4rem; }
  .cab { justify-content: flex-start; gap: 0.65rem; text-align: left; padding: 0.55rem 0.7rem; border-radius: 12px; background: var(--bg-2); }
  .cab.sel { border-color: var(--accent); box-shadow: inset 0 0 0 1px var(--accent); }
  .cn { display: grid; min-width: 0; }
  .cn small { color: var(--fg-2); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .lp-on { margin: -0.2rem 0 0; text-align: center; font-size: 0.85rem; color: var(--fg-2); }
  .launching {
    display: grid; justify-items: center; gap: 0.5rem; text-align: center;
    margin: -0.9rem; padding: 1rem 0.9rem 1.1rem; border-radius: 16px;
    background: var(--neon-panel); color: var(--neon-text);
  }
  .launching :global(.progress) { max-width: 420px; }
  .launching .launch-log { width: 100%; }
  .lp-logo { width: min(100%, 260px); }
  .launching h3 { margin: 0; font-size: 18px; line-height: 1.2; }
  .lp-to { margin: 0; font-size: 13px; color: var(--neon-muted); }
  .warn { color: var(--warn); margin: 0; }
  .ok { color: var(--ok); margin: 0; font-weight: 600; }
  .hint { margin: 0; font-size: 0.82rem; color: var(--fg-2); }

  .similar { padding: 1.2rem 1rem 0; }
  .similar h4 { margin-bottom: 0.6rem; }
  .row { display: grid; grid-auto-flow: column; grid-auto-columns: minmax(150px, 42%); gap: 0.6rem; overflow-x: auto; scroll-snap-type: x mandatory; scrollbar-width: none; padding-bottom: 0.4rem; }
  .cell { scroll-snap-align: start; display: grid; }
  @media (min-width: 760px) { .row { grid-auto-columns: 190px; } }
</style>
