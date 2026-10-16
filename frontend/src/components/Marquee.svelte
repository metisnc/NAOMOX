<script lang="ts">
  // Fronton rétroéclairé : le logo du jeu mis en valeur sur un panneau lumineux
  // teinté aux couleurs du système. Sans logo, le nom du jeu en typographie arcade.
  import { systemColor } from '../lib/catalog';
  import { analyse, cachedTone, type LogoTone } from '../lib/logo';

  let {
    image,
    name,
    system,
    size = 'md',
    lit = false,
  }: { image: string | null; name: string; system: string; size?: 'sm' | 'md' | 'lg'; lit?: boolean } = $props();

  let tone = $state<LogoTone | undefined>(undefined);
  let failed = $state(false);
  $effect(() => {
    tone = image ? cachedTone(image) : undefined;
    failed = false;
  });

  function onload(e: Event) {
    tone = analyse(e.currentTarget as HTMLImageElement);
  }
</script>

<div
  class="marquee {size} {tone ?? 'pending'}"
  class:lit
  class:nologo={!image || failed}
  style="--sys:{systemColor(system)}"
>
  {#if image && !failed}
    <img src={image} alt={name} loading="lazy" decoding="async" crossorigin="anonymous" {onload} onerror={() => (failed = true)} />
  {:else}
    <span class="title">{name}</span>
  {/if}
</div>

<style>
  .marquee {
    position: relative;
    display: grid;
    width: 100%;
    box-sizing: border-box;
    place-items: center;
    overflow: hidden;
    aspect-ratio: 16 / 7;
    padding: 8% 7%;
    border-radius: inherit;
    isolation: isolate;
    background:
      radial-gradient(120% 90% at 50% 0%, color-mix(in srgb, var(--sys) 34%, transparent), transparent 70%),
      linear-gradient(180deg, #1b2230, #0d1118);
  }
  /* Néon du fronton : lisère lumineux en bas. */
  .marquee::after {
    content: '';
    position: absolute;
    inset: auto 12% 0;
    height: 2px;
    background: var(--sys);
    box-shadow: 0 0 12px 2px var(--sys);
    opacity: 0.7;
    z-index: -1;
  }
  .marquee.dark {
    background:
      radial-gradient(130% 100% at 50% 30%, #ffffff, #e9eef5 55%, color-mix(in srgb, var(--sys) 30%, #cfd8e3));
  }
  .marquee.dark::after { opacity: 0.45; }
  .marquee.lg { aspect-ratio: auto; padding: 0; background: none; }
  .marquee.lg::after { display: none; }

  /* Zone du logo identique pour toutes les tuiles (logos recadrés côté serveur) :
     un logo large s'appuie sur la largeur, un logo haut sur la hauteur. */
  img {
    position: absolute;
    left: 9%;
    top: 13%;
    width: 82%;
    height: 70%;
    object-fit: contain;
    filter: drop-shadow(0 3px 6px rgb(0 0 0 / 0.55));
  }
  .marquee.dark img { filter: drop-shadow(0 2px 3px rgb(0 0 0 / 0.25)); }
  .marquee.lg img {
    position: static;
    width: auto;
    height: auto;
    max-width: 100%;
    max-height: 150px;
    filter: drop-shadow(0 0 1px #fff) drop-shadow(0 0 18px color-mix(in srgb, var(--sys) 70%, transparent))
      drop-shadow(0 6px 14px rgb(0 0 0 / 0.7));
  }
  .marquee.lg.dark img {
    filter: drop-shadow(0 0 2px #fff) drop-shadow(0 0 2px #fff) drop-shadow(0 0 22px rgb(255 255 255 / 0.85));
  }
  /* Survol : la tuile s'illumine, le logo garde sa taille. */
  .lit::after { opacity: 1; }

  .title {
    font-weight: 900;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    text-align: center;
    line-height: 1.05;
    color: #fff;
    text-shadow: 0 0 10px var(--sys), 0 0 2px var(--sys);
    font-size: clamp(0.8rem, 3.6vw, 1.15rem);
    display: -webkit-box;
    -webkit-line-clamp: 3;
    line-clamp: 3;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
  .sm .title { font-size: 0.75rem; }
  .lg .title { font-size: clamp(1.6rem, 7vw, 2.6rem); }
</style>
