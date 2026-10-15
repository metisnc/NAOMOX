import { expect, test } from '@playwright/test';

// Pré-requis (voir docs/TESTING.md) : instance NAOMOX vierge dont le sous-réseau de
// découverte contient un mock NetDIMM, et une ROM factice `n1-naomox_e2e_test.bin.gz`
// dans son dossier roms/.
const GAME = 'n1-naomox_e2e_test';
const SHOTS = 'e2e/.results/screens';

test('ajouter une borne, scanner, lancer un jeu fictif jusqu’à « Terminé »', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('header .brand')).toHaveText('NAOMOX');
  await expect(page.locator('header .live')).toContainText('en direct');

  // 1. Découverte de la NetDIMM virtuelle puis ajout de la borne.
  await page.getByRole('link', { name: 'Bornes' }).click();
  await page.getByRole('button', { name: 'Rechercher' }).click();
  const found = page.getByRole('dialog', { name: 'Recherche de NetDIMM' });
  await expect(found.getByText('127.0.0.1')).toBeVisible({ timeout: 20_000 });
  await found.getByRole('button', { name: 'Ajouter' }).click();

  const form = page.getByRole('dialog', { name: 'Nouvelle borne' });
  await expect(form.getByLabel('Adresse IP de la NetDIMM')).toHaveValue('127.0.0.1');
  await form.getByLabel('Nom').fill('Borne virtuelle');
  await form.getByLabel('Type de borne').selectOption('Sega Naomi2');
  await form.getByRole('button', { name: 'Enregistrer' }).click();
  const card = page.locator('article.cab', { hasText: 'Borne virtuelle' });
  await expect(card).toContainText('en ligne', { timeout: 15_000 });
  await page.screenshot({ path: `${SHOTS}/1-bornes.png`, fullPage: true });

  // 2. Infos NetDIMM (firmware du mock : 4.03).
  await card.getByRole('button', { name: 'Infos' }).click();
  await expect(page.getByRole('dialog').getByText('4.03')).toBeVisible();
  await page.keyboard.press('Escape');

  // 3. Scan des ROMs : la ROM factice apparaît dans la liste des jeux.
  await page.getByRole('link', { name: 'Réglages' }).click();
  await page.getByRole('button', { name: 'Scanner' }).click();
  await expect(page.locator('.toast', { hasText: '1 nouvelle' })).toBeVisible({ timeout: 10_000 });

  // 4. Lancement depuis l'onglet Jeux.
  await page.getByRole('link', { name: 'Jeux' }).click();
  await page.getByPlaceholder('Jeu, éditeur, genre, année…').fill('naomox_e2e');
  await page.getByRole('button', { name: new RegExp(GAME) }).click();
  const sheet = page.getByRole('dialog', { name: GAME });
  await page.screenshot({ path: `${SHOTS}/2-fiche.png` });
  await sheet.getByRole('button', { name: '▶ Lancer sur Borne virtuelle' }).click();

  // 5. Suivi en direct dans la fiche, puis « Terminé » dans l'activité.
  await expect(sheet.locator('.job')).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/3-transfert.png` });
  await expect(sheet.getByText('tourne sur Borne virtuelle')).toBeVisible({ timeout: 60_000 });
  await expect(page.locator('.toast.ok', { hasText: 'lancé sur Borne virtuelle' })).toBeVisible();
  await page.keyboard.press('Escape');
  await page.getByRole('link', { name: 'Activité' }).click();
  await expect(page.locator('.history li').first()).toContainText('Terminé');
  await expect(page.locator('.history li').first()).toContainText(GAME);
  await page.screenshot({ path: `${SHOTS}/4-activite.png`, fullPage: true });

  // 6. La borne affiche le jeu en cours.
  await page.getByRole('link', { name: 'Bornes' }).click();
  await expect(card).toContainText(GAME);
});
