import { defineConfig, devices } from '@playwright/test';

// Test de bout en bout de l'interface contre une instance NAOMOX + mock NetDIMM.
// Utilise le navigateur installé (Edge ou Chrome) : aucun téléchargement de navigateur.
//   NAOMOX_E2E_URL=http://10.185.10.230:8081 npx playwright test
export default defineConfig({
  testDir: 'e2e',
  timeout: 90_000,
  retries: 0,
  reporter: [['list']],
  outputDir: 'e2e/.results',
  use: {
    baseURL: process.env.NAOMOX_E2E_URL ?? 'http://10.185.10.230:8081',
    channel: process.env.NAOMOX_E2E_BROWSER ?? 'msedge',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [{ name: 'mobile', use: { ...devices['Pixel 7'], channel: process.env.NAOMOX_E2E_BROWSER ?? 'msedge' } }],
});
