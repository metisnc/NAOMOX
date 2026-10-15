import { svelte } from '@sveltejs/vite-plugin-svelte';
import { defineConfig, loadEnv } from 'vite';

// En dev, l'API est celle du CT (ou d'un `naomox serve` local) : NAOMOX_API=http://hôte:port
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', 'NAOMOX_');
  return {
    plugins: [svelte()],
    build: { outDir: 'dist', emptyOutDir: true, target: 'es2020' },
    server: { proxy: { '/api': { target: env.NAOMOX_API ?? 'http://10.185.10.230', changeOrigin: true } } },
  };
});
