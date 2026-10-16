// Messages et progression d'un job, dans l'esprit du launcher WiPiNetbooter-NG.

import type { Job } from './types';

export function jobMessage(j: Job): string {
  const to = j.cabinet_name;
  switch (j.state) {
    case 'queued':
      return `En attente de ${to}…`;
    case 'decompress':
      return 'Préparation du jeu…';
    case 'connecting':
      return `Connexion à ${to}…`;
    case 'uploading':
      return `Transfert vers ${to}…`;
    case 'verifying':
      return 'Vérification du transfert…';
    case 'rebooting':
      return 'Démarrage du jeu…';
    case 'retrying':
      return j.message ?? `${to} ne répond pas, nouvel essai…`;
    case 'done':
      return j.kind === 'launch' ? 'Jeu lancé — bon jeu !' : 'Envoyé — suivez les instructions à l’écran de la borne.';
    case 'cancelled':
      return 'Transfert annulé.';
    case 'error':
      return j.message ?? 'Échec du transfert.';
  }
}

/** Pourcentage affiché, ou null pour une barre « en cours » sans durée connue. */
export function jobPercent(j: Job): number | null {
  if (j.state === 'decompress' || j.state === 'uploading') return j.total ? j.percent : null;
  if (j.state === 'verifying' || j.state === 'rebooting' || j.state === 'done') return 100;
  return null;
}

export const jobTone = (j: Job): '' | 'ok' | 'err' =>
  j.state === 'done' ? 'ok' : j.state === 'error' || j.state === 'cancelled' ? 'err' : '';
