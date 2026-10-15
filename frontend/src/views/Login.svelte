<script lang="ts">
  import { api } from '../lib/api';
  import { app } from '../lib/state.svelte';

  let password = $state('');
  let busy = $state(false);

  async function submit(e: SubmitEvent) {
    e.preventDefault();
    busy = true;
    const ok = await app.run(() => api.post('/auth/login', { password }));
    busy = false;
    if (ok) {
      app.auth = { enabled: true, authenticated: true };
      await app.loadAll();
    }
  }
</script>

<form class="login card stack" onsubmit={submit}>
  <h1>NAOMOX</h1>
  <label class="field">Mot de passe
    <!-- svelte-ignore a11y_autofocus -->
    <input type="password" autocomplete="current-password" bind:value={password} autofocus />
  </label>
  <button class="primary" disabled={busy || !password}>Se connecter</button>
</form>

<style>
  .login { width: min(92vw, 360px); margin: 20dvh auto 0; }
  h1 { color: var(--accent); letter-spacing: 0.16em; text-align: center; }
</style>
