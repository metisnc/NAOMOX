// Client de l'API NAOMOX (/api/v1). Toute écriture porte l'en-tête anti-CSRF.

export const API = '/api/v1';

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public detail: Record<string, unknown> = {},
  ) {
    super(message);
  }
  get code(): string | undefined {
    return this.detail.error as string | undefined;
  }
}

async function request<T>(method: string, path: string, body?: unknown, raw?: BodyInit): Promise<T> {
  const headers: Record<string, string> = { Accept: 'application/json' };
  if (method !== 'GET') headers['X-Requested-With'] = 'naomox';
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  let res: Response;
  try {
    res = await fetch(API + path, {
      method,
      headers,
      credentials: 'same-origin',
      body: raw ?? (body !== undefined ? JSON.stringify(body) : undefined),
    });
  } catch {
    throw new ApiError(0, 'serveur NAOMOX injoignable');
  }
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  const data = text ? JSON.parse(text) : undefined;
  if (!res.ok) {
    const d = data?.detail;
    if (Array.isArray(d)) {
      // Erreur de validation FastAPI (422)
      const msg = d.map((e: { loc?: string[]; msg: string }) => `${e.loc?.slice(-1)[0] ?? ''} : ${e.msg}`).join(', ');
      throw new ApiError(res.status, msg);
    }
    const message = typeof d === 'string' ? d : (d?.message ?? `erreur ${res.status}`);
    throw new ApiError(res.status, message, typeof d === 'object' && d ? d : {});
  }
  return data as T;
}

export const api = {
  get: <T>(p: string) => request<T>('GET', p),
  post: <T>(p: string, body?: unknown) => request<T>('POST', p, body ?? {}),
  patch: <T>(p: string, body: unknown) => request<T>('PATCH', p, body),
  put: <T>(p: string, body: unknown) => request<T>('PUT', p, body),
  del: <T = void>(p: string) => request<T>('DELETE', p),
  upload: <T>(p: string, form: FormData) => request<T>('POST', p, undefined, form),
};

/** Upload avec progression (fetch ne la fournit pas). */
export function uploadWithProgress(
  path: string,
  file: File,
  onProgress: (pct: number) => void,
): Promise<void> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', API + path);
    xhr.setRequestHeader('X-Requested-With', 'naomox');
    xhr.upload.onprogress = (e) => e.lengthComputable && onProgress(Math.round((e.loaded * 100) / e.total));
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) return resolve();
      let msg = `erreur ${xhr.status}`;
      try {
        msg = JSON.parse(xhr.responseText).detail.message ?? msg;
      } catch {
        /* réponse non JSON */
      }
      reject(new ApiError(xhr.status, msg));
    };
    xhr.onerror = () => reject(new ApiError(0, 'serveur NAOMOX injoignable'));
    const form = new FormData();
    form.append('file', file);
    xhr.send(form);
  });
}
