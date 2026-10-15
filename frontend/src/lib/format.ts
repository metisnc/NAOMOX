import type { Job, JobState } from './types';

export const SYSTEM_SHORT: Record<string, string> = {
  'Sega Naomi': 'Naomi',
  'Sega Naomi2': 'Naomi 2',
  'Sammy Atomiswave': 'Atomiswave',
  'Sega Chihiro': 'Chihiro',
  'Sega Triforce': 'Triforce',
};

export const STATE_LABEL: Record<JobState, string> = {
  queued: 'En attente',
  decompress: 'Décompression',
  connecting: 'Connexion',
  uploading: 'Envoi',
  rebooting: 'Redémarrage',
  retrying: 'Nouvel essai',
  done: 'Terminé',
  error: 'Échec',
  cancelled: 'Annulé',
};

export const ERROR_HELP: Record<string, string> = {
  unreachable: 'La NetDIMM ne répond pas : borne éteinte, câble réseau ou mauvaise IP ?',
  refused: 'Connexion refusée : la NetDIMM n’écoute pas (mode, firmware ou IP ?).',
  timeout: 'La NetDIMM a cessé de répondre pendant le transfert.',
  disconnected: 'Connexion coupée pendant l’envoi.',
  protocol: 'Réponse inattendue de la NetDIMM (firmware incompatible ?).',
  rom_missing: 'Le fichier ROM est absent du serveur.',
  file: 'Fichier ROM illisible ou corrompu.',
  internal: 'Erreur interne NAOMOX, voir le journal.',
};

export const isFinal = (j: Job) => j.state === 'done' || j.state === 'error' || j.state === 'cancelled';

export function bytes(n: number): string {
  if (n < 1024) return `${n} o`;
  const u = ['Ko', 'Mo', 'Go', 'To'];
  let i = -1;
  do {
    n /= 1024;
    i++;
  } while (n >= 1024 && i < u.length - 1);
  return `${n.toFixed(n < 10 ? 1 : 0)} ${u[i]}`;
}

export function ago(ts: number | null): string {
  if (!ts) return '—';
  const s = Math.max(0, Date.now() / 1000 - ts);
  if (s < 60) return 'à l’instant';
  if (s < 3600) return `il y a ${Math.floor(s / 60)} min`;
  if (s < 86400) return `il y a ${Math.floor(s / 3600)} h`;
  return new Date(ts * 1000).toLocaleDateString('fr-FR', { day: 'numeric', month: 'short' });
}

export function romLabel(rom: string | null, names: Map<string, string>): string {
  if (!rom) return '—';
  return names.get(rom) ?? rom.replace(/\.bin(\.gz)?$/, '');
}
