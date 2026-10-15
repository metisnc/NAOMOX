<script lang="ts">
  import { onMount } from 'svelte';
  import { app } from './lib/state.svelte';
  import JobBanner from './components/JobBanner.svelte';
  import Toasts from './components/Toasts.svelte';
  import Login from './views/Login.svelte';
  import Games from './views/Games.svelte';
  import Cabinets from './views/Cabinets.svelte';
  import Activity from './views/Activity.svelte';
  import SettingsView from './views/Settings.svelte';

  const tabs = [
    { path: '/', label: 'Jeux', icon: 'M4 6h16v12H4zM8 10h2m-1-1v2m6 0h.01M17 11h.01' },
    { path: '/bornes', label: 'Bornes', icon: 'M7 3h10v18H7zM9 6h6v5H9zM10 15h.01M14 15h.01' },
    { path: '/activite', label: 'Activité', icon: 'M3 12h4l3-8 4 16 3-8h4' },
    { path: '/reglages', label: 'Réglages', icon: 'M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6zM4 12h2m12 0h2M12 4v2m0 12v2' },
  ];

  let route = $state(location.hash.slice(1) || '/');
  onMount(() => {
    const onHash = () => (route = location.hash.slice(1) || '/');
    window.addEventListener('hashchange', onHash);
    app.init();
    return () => window.removeEventListener('hashchange', onHash);
  });
</script>

{#if app.loading}
  <div class="splash">NAOMOX</div>
{:else if app.auth && !app.auth.authenticated}
  <Login />
{:else}
  <header>
    <a class="brand" href="#/">NAOMOX</a>
    <span class="live" class:on={app.live} title={app.live ? 'Temps réel connecté' : 'Temps réel déconnecté'}>
      <span class="dot" class:on={app.live} class:off={!app.live}></span>
      {app.live ? 'en direct' : 'hors ligne'}
    </span>
  </header>
  <JobBanner />
  <main>
    {#if route === '/bornes'}
      <Cabinets />
    {:else if route === '/activite'}
      <Activity />
    {:else if route === '/reglages'}
      <SettingsView />
    {:else}
      <Games />
    {/if}
  </main>
  <nav>
    {#each tabs as t (t.path)}
      <a href={'#' + t.path} class:active={route === t.path}>
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d={t.icon} /></svg>
        <span>{t.label}</span>
        {#if t.path === '/activite' && app.activeJobs.length}<b class="count">{app.activeJobs.length}</b>{/if}
      </a>
    {/each}
  </nav>
{/if}
<Toasts />

<style>
  .splash { display: grid; place-items: center; height: 100dvh; font-weight: 800; letter-spacing: 0.2em; color: var(--accent); }
  header {
    position: sticky; top: 0; z-index: 20;
    display: flex; align-items: center; justify-content: space-between;
    padding: calc(env(safe-area-inset-top, 0px) + 0.6rem) 1rem 0.6rem;
    background: color-mix(in srgb, var(--bg) 88%, transparent);
    backdrop-filter: blur(10px);
    border-bottom: 1px solid var(--line);
  }
  .brand { font-weight: 900; letter-spacing: 0.16em; color: var(--accent); text-decoration: none; }
  .live { display: flex; align-items: center; gap: 0.4rem; font-size: 0.8rem; color: var(--fg-2); }
  nav {
    position: fixed; bottom: 0; left: 0; right: 0; z-index: 30;
    display: grid; grid-template-columns: repeat(4, 1fr);
    height: calc(var(--nav-h) + var(--safe-b)); padding-bottom: var(--safe-b);
    background: var(--bg-2); border-top: 1px solid var(--line);
  }
  nav a {
    position: relative; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 2px;
    color: var(--fg-2); text-decoration: none; font-size: 0.75rem;
  }
  nav a.active { color: var(--accent); }
  nav svg { width: 24px; height: 24px; fill: none; stroke: currentColor; stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; }
  .count {
    position: absolute; top: 6px; left: calc(50% + 6px);
    background: var(--accent); color: var(--accent-fg); font-size: 0.68rem; border-radius: 99px; padding: 0 0.35rem;
  }
  @media (min-width: 900px) {
    nav { left: 50%; transform: translateX(-50%); bottom: 12px; width: 520px; border-radius: 18px; border: 1px solid var(--line); height: var(--nav-h); padding: 0; }
  }
</style>
