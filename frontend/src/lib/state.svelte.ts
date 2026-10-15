// État global réactif (runes Svelte 5) alimenté par l'API et le flux SSE.

import { API, ApiError, api } from './api';
import type { Cabinet, CabinetStatus, Game, Job, Settings, Systems } from './types';

export interface Toast {
  id: number;
  kind: 'info' | 'ok' | 'error';
  text: string;
}

class AppState {
  games = $state<Game[]>([]);
  cabinets = $state<Cabinet[]>([]);
  jobs = $state<Record<string, Job>>({});
  systems = $state<Systems | null>(null);
  settings = $state<Settings | null>(null);
  auth = $state<{ enabled: boolean; authenticated: boolean } | null>(null);
  live = $state(false);
  loading = $state(true);
  toasts = $state<Toast[]>([]);

  names = $derived(new Map(this.games.map((g) => [g.rom, g.name])));
  activeJobs = $derived(
    Object.values(this.jobs)
      .filter((j) => !['done', 'error', 'cancelled'].includes(j.state))
      .sort((a, b) => a.created - b.created),
  );

  #es: EventSource | null = null;
  #toastId = 0;
  #refreshTimer: ReturnType<typeof setTimeout> | null = null;

  async init(): Promise<void> {
    this.loading = true;
    try {
      this.auth = await api.get('/auth');
      if (this.auth?.authenticated) await this.loadAll();
    } catch (e) {
      this.toast('error', (e as Error).message);
    } finally {
      this.loading = false;
    }
  }

  async loadAll(): Promise<void> {
    const [games, cabinets, jobs, systems, settings] = await Promise.all([
      api.get<Game[]>('/games'),
      api.get<Cabinet[]>('/cabinets'),
      api.get<Job[]>('/jobs'),
      api.get<Systems>('/systems'),
      api.get<Settings>('/settings'),
    ]);
    this.games = games;
    this.cabinets = cabinets;
    this.jobs = Object.fromEntries(jobs.map((j) => [j.id, j]));
    this.systems = systems;
    this.settings = settings;
    this.connect();
  }

  async refreshGames(): Promise<void> {
    this.games = await api.get<Game[]>('/games');
  }

  async refreshCabinets(): Promise<void> {
    this.cabinets = await api.get<Cabinet[]>('/cabinets');
  }

  /** Rafraîchissement groupé des bornes (après la fin d'un job, plusieurs événements arrivent). */
  scheduleCabinetRefresh(): void {
    if (this.#refreshTimer) clearTimeout(this.#refreshTimer);
    this.#refreshTimer = setTimeout(() => this.refreshCabinets().catch(() => {}), 400);
  }

  connect(): void {
    this.#es?.close();
    const es = new EventSource(`${API}/events`);
    this.#es = es;
    es.onopen = () => {
      // Après une coupure, on resynchronise ce qui a pu être manqué.
      if (!this.live) {
        this.live = true;
        api.get<Job[]>('/jobs').then((jobs) => (this.jobs = Object.fromEntries(jobs.map((j) => [j.id, j]))));
        this.refreshCabinets().catch(() => {});
      }
    };
    es.onerror = () => {
      this.live = false;
    };
    es.addEventListener('job', (ev) => {
      const job: Job = JSON.parse((ev as MessageEvent).data);
      const prev = this.jobs[job.id];
      this.jobs[job.id] = job;
      const cab = this.cabinets.find((c) => c.id === job.cabinet_id);
      if (cab) cab.status.current_job = ['done', 'error', 'cancelled'].includes(job.state) ? null : job;
      if (prev && prev.state !== job.state) {
        if (job.state === 'done' && job.kind === 'launch')
          this.toast('ok', `${this.names.get(job.rom) ?? job.rom} lancé sur ${job.cabinet_name}`);
        if (job.state === 'error') this.toast('error', `${job.cabinet_name} : ${job.message ?? 'échec'}`);
        if (['done', 'error', 'cancelled'].includes(job.state)) this.scheduleCabinetRefresh();
      }
    });
    es.addEventListener('cabinet', (ev) => {
      const st: CabinetStatus = JSON.parse((ev as MessageEvent).data);
      const cab = this.cabinets.find((c) => c.id === st.id);
      if (cab) cab.status = st;
    });
  }

  toast(kind: Toast['kind'], text: string, ms = 4500): void {
    const id = ++this.#toastId;
    this.toasts.push({ id, kind, text });
    setTimeout(() => (this.toasts = this.toasts.filter((t) => t.id !== id)), ms);
  }

  /** Exécute une action et affiche l'erreur éventuelle. */
  async run<T>(fn: () => Promise<T>, okText?: string): Promise<T | undefined> {
    try {
      const r = await fn();
      if (okText) this.toast('ok', okText);
      return r;
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) {
        this.auth = { enabled: true, authenticated: false };
      }
      this.toast('error', (e as Error).message);
      return undefined;
    }
  }

  setGame(updated: Game): void {
    const i = this.games.findIndex((g) => g.rom === updated.rom);
    if (i >= 0) this.games[i] = updated;
  }
}

export const app = new AppState();
