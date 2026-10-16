export interface Game {
  rom: string;
  name: string;
  system: string;
  manufacturer: string;
  year: string;
  genre: string;
  rating: string;
  orientation: string;
  controls: string;
  enabled: boolean;
  favourite: boolean;
  game_id: string;
  image: string | null;
  video: string | null;
  present: boolean;
  size: number | null;
  plays: number;
  last_played: number | null;
}

export type JobState =
  | 'queued'
  | 'decompress'
  | 'connecting'
  | 'uploading'
  | 'verifying'
  | 'rebooting'
  | 'retrying'
  | 'done'
  | 'error'
  | 'cancelled';

export interface Job {
  id: string;
  cabinet_id: string;
  cabinet_name: string;
  ip: string;
  kind: 'launch' | 'firmware' | 'diag';
  rom: string;
  source: 'user' | 'autoboot' | 'server';
  state: JobState;
  done: number;
  total: number;
  percent: number;
  error_kind: string | null;
  message: string | null;
  crc: string | null;
  attempts: number;
  created: number;
  started: number | null;
  ended: number | null;
  log?: string[];
}

export interface CabinetStatus {
  id: string;
  online: boolean | null;
  since: number | null;
  last_probe: number | null;
  busy: boolean;
  current_job: Job | null;
  queued: number;
  game: string | null;
  launched_at: number | null;
  time_hack: { enabled: boolean; last: number | null; ok: boolean | null };
}

export interface CabinetFields {
  name: string;
  ip: string;
  type: string;
  enabled: boolean;
  default_game: string | null;
  time_hack: boolean;
  server_mode: boolean;
  osm_theme: 'dark' | 'light';
  osm_mode: 'once' | 'replay';
}

export interface Cabinet extends CabinetFields {
  id: string;
  status: CabinetStatus;
}

export interface Systems {
  systems: string[];
  dimm_types: string[];
  compatibility: Record<string, string[]>;
  firmware_versions: string[];
  logos: Record<string, string | null>;
}

export interface Settings {
  cabinet_subnet: string;
  netdimm_port: number;
  timehack_interval: number;
  auth_enabled: boolean;
  version: string;
  hostname: string;
  network_name: string;
  network_name_ok: boolean;
  network_name_error: string | null;
}

export interface HistoryEntry {
  ts: number;
  job: string;
  kind: string;
  rom: string;
  cabinet_id: string;
  cabinet: string;
  state: string;
  error_kind: string | null;
  message: string | null;
  source: string;
  duration: number;
}

export interface CabinetChoice {
  id: string;
  name: string;
  ip: string;
  type: string;
  online: boolean;
}

export interface DimmInfo {
  firmware: string;
  memory_mb: number;
  game_memory_bytes: number;
  current_game_crc: string;
  current_game_size: number;
  crc_status: string;
  control_address: string;
}

export interface FileEntry {
  name: string;
  size: number;
  mtime: number;
}
