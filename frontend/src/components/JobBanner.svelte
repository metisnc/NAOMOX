<script lang="ts">
  import { app } from '../lib/state.svelte';
  import JobCard from './JobCard.svelte';
</script>

{#if app.activeJobs.length}
  <section class="banner">
    {#each app.activeJobs as job (job.id)}
      <JobCard {job} />
    {/each}
  </section>
{/if}

<style>
  .banner {
    position: sticky; top: 52px; z-index: 15; display: grid; gap: 0.5rem;
    padding: 0.6rem 1rem; max-width: 1100px; margin: 0 auto;
    background: color-mix(in srgb, var(--bg) 92%, transparent); backdrop-filter: blur(8px);
  }
</style>
