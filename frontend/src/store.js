/**
 * Tiny reactive store + query cache.
 *
 * The app has a handful of shared server values (me, billing status, library,
 * categories) that several screens read and mutations invalidate. This gives them a
 * cache with subscriptions, without pulling in a query library.
 */

const state = {
  me: null,
  billing: null,
  aiUsage: null,
  categories: null,
  ready: false,
};

const listeners = new Set();

export function getState() {
  return state;
}

export function setState(patch) {
  Object.assign(state, patch);
  for (const listener of listeners) listener(state);
}

export function subscribe(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

// ------------------------------------------------------------------ query cache

const cache = new Map(); // key -> { value, at, promise }
const DEFAULT_TTL = 30_000;

/**
 * Cached fetch. Returns the cached value when fresh, de-duplicates concurrent calls.
 * @param {string} key
 * @param {() => Promise<any>} loader
 * @param {{ ttl?: number, force?: boolean }} [options]
 */
export async function query(key, loader, options = {}) {
  const ttl = options.ttl ?? DEFAULT_TTL;
  const entry = cache.get(key);
  const now = Date.now();

  if (!options.force && entry) {
    if (entry.promise) return entry.promise;
    if (now - entry.at < ttl) return entry.value;
  }

  const promise = loader()
    .then((value) => {
      cache.set(key, { value, at: Date.now() });
      return value;
    })
    .catch((error) => {
      cache.delete(key);
      throw error;
    });

  cache.set(key, { ...(entry || {}), promise });
  return promise;
}

export function peek(key) {
  const entry = cache.get(key);
  return entry && !entry.promise ? entry.value : undefined;
}

/** Drop cache entries whose key starts with any of the given prefixes. */
export function invalidate(...prefixes) {
  for (const key of [...cache.keys()]) {
    if (prefixes.some((prefix) => key.startsWith(prefix))) cache.delete(key);
  }
}

export function invalidateAll() {
  cache.clear();
}

/** Write a value straight into the cache (optimistic updates). */
export function setQueryData(key, value) {
  cache.set(key, { value, at: Date.now() });
}

// ------------------------------------------------------------------ keys

export const keys = {
  me: 'me',
  stats: 'me:stats',
  preferences: 'me:preferences',
  billing: 'billing:status',
  providers: 'billing:providers',
  aiUsage: 'ai:usage',
  categories: 'library:categories',
  library: (params = {}) => `library:${JSON.stringify(params)}`,
  userBook: (id) => `library:book:${id}`,
  entries: (bookId, params = {}) => `entries:${bookId}:${JSON.stringify(params)}`,
  entry: (id) => `entry:${id}`,
  tags: 'tags',
  search: (q) => `search:${q}`,
  conversations: 'ai:conversations',
  conversation: (id) => `ai:conversation:${id}`,
};
