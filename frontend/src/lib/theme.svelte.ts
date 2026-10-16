// Thème clair / sombre (néon). Sombre par défaut, choix mémorisé sur l'appareil.

export type Theme = 'dark' | 'light';
const KEY = 'naomox.theme';

function initial(): Theme {
  try {
    return localStorage.getItem(KEY) === 'light' ? 'light' : 'dark';
  } catch {
    return 'dark';
  }
}

class ThemeState {
  current = $state<Theme>(initial());

  set(t: Theme): void {
    this.current = t;
    const root = document.documentElement;
    if (t === 'light') root.dataset.theme = 'light';
    else delete root.dataset.theme;
    document.querySelector('meta[name=theme-color]')?.setAttribute('content', t === 'light' ? '#f3f4fa' : '#07080d');
    try {
      localStorage.setItem(KEY, t);
    } catch {
      /* stockage indisponible */
    }
  }

  toggle(): void {
    this.set(this.current === 'dark' ? 'light' : 'dark');
  }
}

export const theme = new ThemeState();
