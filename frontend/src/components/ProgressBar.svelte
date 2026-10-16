<script lang="ts">
  // Barre de progression néon reprise du launcher WiPiNetbooter-NG :
  // dégradé cyan → magenta, pourcentage en gras au centre, balayage si durée inconnue.
  let { value = null, size = 'md' }: { value?: number | null; size?: 'sm' | 'md' } = $props();

  const pct = $derived(value === null ? null : Math.max(0, Math.min(100, Math.round(value))));
</script>

<div
  class="progress {size}"
  class:indeterminate={pct === null}
  role="progressbar"
  aria-valuemin="0"
  aria-valuemax="100"
  aria-valuenow={pct ?? undefined}
>
  {#key pct === null}<div class="fill" style:width={pct === null ? undefined : `${pct}%`}></div>{/key}
  {#if pct !== null}<span>{pct} %</span>{/if}
</div>

<style>
  .progress {
    position: relative;
    width: 100%;
    height: 22px;
    border-radius: 11px;
    background: var(--neon-track);
    border: 1px solid var(--neon-line);
    overflow: hidden;
  }
  .progress.sm { height: 16px; border-radius: 8px; }
  .fill {
    height: 100%;
    width: 0;
    background: linear-gradient(90deg, var(--neon-cyan), var(--neon-magenta));
    box-shadow: 0 0 12px color-mix(in srgb, var(--neon-magenta) 55%, transparent);
    transition: width 0.3s linear;
  }
  .indeterminate .fill { width: 30%; animation: sweep 1.2s ease-in-out infinite; }
  @keyframes sweep { from { transform: translateX(-100%); } to { transform: translateX(340%); } }
  span {
    position: absolute;
    inset: 0;
    display: grid;
    place-items: center;
    font-size: 13px;
    font-weight: 800;
    color: #fff;
    text-shadow: 0 1px 2px rgb(0 0 0 / 0.7);
    font-variant-numeric: tabular-nums;
  }
  .sm span { font-size: 11px; }
</style>
