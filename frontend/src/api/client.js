/**
 * Centralised Remarka API client.
 *
 * Framework-agnostic ES module: no fetch() calls belong anywhere else in the frontend.
 * Handles base URL, auth token, timeouts, JSON, and the unified backend error envelope
 * `{ "error": { "code": "...", "message": "..." } }`.
 *
 * Types for every DTO live in ./types.d.ts, so TypeScript and editors get full typing
 * without changing how this module is imported.
 */

const DEFAULT_TIMEOUT_MS = 30000;
const TOKEN_STORAGE_KEY = 'remarka.access_token';

/** Error thrown for every non-2xx response, carrying the backend error code. */
export class ApiError extends Error {
  /**
   * @param {number} status
   * @param {string} code
   * @param {string} message
   * @param {unknown} [details]
   */
  constructor(status, code, message, details) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.details = details;
  }

  get isUnauthorized() {
    return this.status === 401;
  }

  get isForbidden() {
    return this.status === 403;
  }

  get isNotFound() {
    return this.status === 404;
  }

  get isConflict() {
    return this.status === 409;
  }

  get isValidation() {
    return this.status === 422;
  }

  get isRateLimited() {
    return this.status === 429;
  }

  get isAiLimitReached() {
    return this.code === 'AI_LIMIT_REACHED';
  }

  get isServerError() {
    return this.status >= 500;
  }
}

/** Localised, user-safe messages. A traceback is never shown to the user. */
const ERROR_MESSAGES = {
  UNAUTHORIZED: 'Сессия истекла. Откройте приложение заново.',
  TOKEN_EXPIRED: 'Сессия истекла. Откройте приложение заново.',
  INVALID_INIT_DATA: 'Не удалось подтвердить вход через Telegram.',
  FORBIDDEN: 'Нет доступа к этому разделу.',
  ACCOUNT_DISABLED: 'Аккаунт отключён.',
  NOT_FOUND: 'Не найдено.',
  BOOK_NOT_FOUND: 'Книга не найдена в вашей библиотеке.',
  ENTRY_NOT_FOUND: 'Запись не найдена.',
  CONVERSATION_NOT_FOUND: 'Диалог не найден.',
  BOOK_ALREADY_ADDED: 'Эта книга уже есть в вашей библиотеке.',
  VALIDATION_ERROR: 'Проверьте заполненные поля.',
  RATE_LIMIT_EXCEEDED: 'Слишком много запросов. Попробуйте чуть позже.',
  AI_LIMIT_REACHED: 'Бесплатные AI-запросы на этот месяц закончились.',
  PROVIDER_ERROR: 'Сервис временно недоступен. Попробуйте позже.',
  AI_NOT_CONFIGURED: 'AI пока не настроен.',
  PAYMENT_PROVIDER_NOT_CONFIGURED: 'Этот способ оплаты пока недоступен.',
  FILE_TOO_LARGE: 'Файл слишком большой.',
  UNSUPPORTED_MEDIA_TYPE: 'Поддерживаются только JPEG, PNG, WebP и GIF.',
  INTERNAL_ERROR: 'Что-то пошло не так. Попробуйте ещё раз.',
  NETWORK_ERROR: 'Нет связи с сервером.',
  TIMEOUT: 'Сервер не ответил вовремя.',
};

/** @param {ApiError} error */
export function errorMessage(error) {
  if (!(error instanceof ApiError)) return ERROR_MESSAGES.INTERNAL_ERROR;
  return ERROR_MESSAGES[error.code] || error.message || ERROR_MESSAGES.INTERNAL_ERROR;
}

function resolveBaseUrl() {
  // Vite-style env, a global set by the host page, or the local dev default.
  try {
    if (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_API_URL) {
      return import.meta.env.VITE_API_URL;
    }
  } catch {
    /* import.meta is unavailable in classic scripts */
  }
  if (typeof window !== 'undefined' && window.REMARKA_API_URL) return window.REMARKA_API_URL;
  return 'http://localhost:8000/api/v1';
}

function readStoredToken() {
  try {
    return localStorage.getItem(TOKEN_STORAGE_KEY);
  } catch {
    return null; // private mode / storage disabled
  }
}

function writeStoredToken(token) {
  try {
    if (token) localStorage.setItem(TOKEN_STORAGE_KEY, token);
    else localStorage.removeItem(TOKEN_STORAGE_KEY);
  } catch {
    /* ignore */
  }
}

export class ApiClient {
  /**
   * @param {{ baseUrl?: string, timeoutMs?: number, onUnauthorized?: () => void }} [options]
   */
  constructor(options = {}) {
    this.baseUrl = (options.baseUrl || resolveBaseUrl()).replace(/\/$/, '');
    this.timeoutMs = options.timeoutMs || DEFAULT_TIMEOUT_MS;
    this.onUnauthorized = options.onUnauthorized || null;
    this.token = readStoredToken();
  }

  setToken(token) {
    this.token = token;
    writeStoredToken(token);
  }

  clearToken() {
    this.setToken(null);
  }

  get isAuthenticated() {
    return Boolean(this.token);
  }

  /**
   * @param {string} path
   * @param {{ method?: string, body?: unknown, query?: Record<string, unknown>, formData?: FormData, signal?: AbortSignal }} [options]
   */
  async request(path, options = {}) {
    const url = new URL(this.baseUrl + path);
    for (const [key, value] of Object.entries(options.query || {})) {
      if (value === undefined || value === null || value === '') continue;
      url.searchParams.set(key, String(value));
    }

    const headers = {};
    if (this.token) headers.Authorization = `Bearer ${this.token}`;

    let body;
    if (options.formData) {
      body = options.formData; // the browser sets the multipart boundary itself
    } else if (options.body !== undefined) {
      headers['Content-Type'] = 'application/json';
      body = JSON.stringify(options.body);
    }

    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), this.timeoutMs);
    if (options.signal) {
      options.signal.addEventListener('abort', () => controller.abort(), { once: true });
    }

    let response;
    try {
      response = await fetch(url.toString(), {
        method: options.method || 'GET',
        headers,
        body,
        signal: controller.signal,
      });
    } catch (cause) {
      clearTimeout(timeout);
      const aborted = cause && cause.name === 'AbortError';
      throw new ApiError(
        0,
        aborted ? 'TIMEOUT' : 'NETWORK_ERROR',
        aborted ? ERROR_MESSAGES.TIMEOUT : ERROR_MESSAGES.NETWORK_ERROR,
      );
    } finally {
      clearTimeout(timeout);
    }

    if (response.status === 204) return null;

    let payload = null;
    const text = await response.text();
    if (text) {
      try {
        payload = JSON.parse(text);
      } catch {
        payload = null;
      }
    }

    if (!response.ok) {
      const envelope = (payload && payload.error) || {};
      const error = new ApiError(
        response.status,
        envelope.code || 'INTERNAL_ERROR',
        envelope.message || response.statusText,
        envelope.details,
      );
      if (error.isUnauthorized) {
        this.clearToken();
        if (this.onUnauthorized) this.onUnauthorized();
      }
      throw error;
    }

    return payload;
  }

  get(path, query, options) {
    return this.request(path, { ...options, method: 'GET', query });
  }

  post(path, body, options) {
    return this.request(path, { ...options, method: 'POST', body });
  }

  patch(path, body, options) {
    return this.request(path, { ...options, method: 'PATCH', body });
  }

  put(path, body, options) {
    return this.request(path, { ...options, method: 'PUT', body });
  }

  delete(path, options) {
    return this.request(path, { ...options, method: 'DELETE' });
  }

  // ---------------------------------------------------------------- auth

  /** Exchange raw Telegram initData for a Remarka session token. */
  async authTelegram(initData) {
    const result = await this.post('/auth/telegram', { init_data: initData });
    this.setToken(result.access_token);
    return result;
  }

  /** Development login, available only while the backend runs with APP_ENV=development. */
  async authDev(telegramId, firstName = 'Dev') {
    const result = await this.post('/auth/dev', {
      telegram_id: telegramId,
      first_name: firstName,
    });
    this.setToken(result.access_token);
    return result;
  }

  // ---------------------------------------------------------------- me

  getMe() {
    return this.get('/me');
  }

  updateMe(patch) {
    return this.patch('/me', patch);
  }

  getStats() {
    return this.get('/me/stats');
  }

  getPreferences() {
    return this.get('/me/preferences');
  }

  updatePreferences(preferences) {
    return this.put('/me/preferences', preferences);
  }

  deleteAccount() {
    return this.delete('/me');
  }

  // ---------------------------------------------------------------- books

  searchBooks(query, limit = 20) {
    return this.get('/books/search', { q: query, limit });
  }

  addBook(book) {
    return this.post('/books', book);
  }

  addManualBook(book) {
    return this.post('/books/manual', book);
  }

  /** @param {File|Blob} file */
  uploadCover(file) {
    const formData = new FormData();
    formData.append('file', file);
    return this.request('/books/cover', { method: 'POST', formData });
  }

  // ---------------------------------------------------------------- library

  getLibrary(params = {}) {
    return this.get('/library', params);
  }

  getCategories() {
    return this.get('/library/categories');
  }

  getUserBook(userBookId) {
    return this.get(`/library/${userBookId}`);
  }

  updateUserBook(userBookId, patch) {
    return this.patch(`/library/${userBookId}`, patch);
  }

  setBookFavorite(userBookId, isFavorite) {
    return this.patch(`/library/${userBookId}`, { is_favorite: isFavorite });
  }

  deleteUserBook(userBookId) {
    return this.delete(`/library/${userBookId}`);
  }

  // ---------------------------------------------------------------- entries

  getBookEntries(userBookId, params = {}) {
    return this.get(`/library/${userBookId}/entries`, params);
  }

  createEntry(userBookId, entry) {
    return this.post(`/library/${userBookId}/entries`, entry);
  }

  getEntries(params = {}) {
    return this.get('/entries', params);
  }

  getEntry(entryId) {
    return this.get(`/entries/${entryId}`);
  }

  updateEntry(entryId, patch) {
    return this.patch(`/entries/${entryId}`, patch);
  }

  setEntryFavorite(entryId, isFavorite) {
    return this.put(`/entries/${entryId}/favorite`, { is_favorite: isFavorite });
  }

  deleteEntry(entryId) {
    return this.delete(`/entries/${entryId}`);
  }

  // ---------------------------------------------------------------- tags & search

  getTags(query) {
    return this.get('/tags', { q: query });
  }

  search(query, limit = 20) {
    return this.get('/search', { q: query, limit });
  }

  // ---------------------------------------------------------------- AI

  getAiUsage() {
    return this.get('/ai/usage');
  }

  getConversations(params = {}) {
    return this.get('/ai/conversations', params);
  }

  createConversation(payload) {
    return this.post('/ai/conversations', payload);
  }

  getConversation(conversationId) {
    return this.get(`/ai/conversations/${conversationId}`);
  }

  deleteConversation(conversationId) {
    return this.delete(`/ai/conversations/${conversationId}`);
  }

  /** Start a new conversation and get the answer in one call. */
  ask(question, contextType = 'all_library', contextUserBookId = null) {
    return this.post('/ai/ask', {
      question,
      context_type: contextType,
      context_user_book_id: contextUserBookId,
    });
  }

  /** Continue an existing conversation. */
  askInConversation(conversationId, question) {
    return this.post(`/ai/conversations/${conversationId}/messages`, { question });
  }

  // ---------------------------------------------------------------- billing

  getBillingStatus() {
    return this.get('/billing/status');
  }

  /** The backend decides which providers the UI may offer. */
  getPaymentProviders() {
    return this.get('/billing/providers');
  }

  createStarsInvoice() {
    return this.post('/billing/telegram-stars/create', { provider: 'telegram_stars' });
  }

  getPaymentStatus(paymentId) {
    return this.get(`/billing/payments/${paymentId}`);
  }

  // ---------------------------------------------------------------- legal

  getLegalDocument(slug) {
    return this.get(`/legal/${slug}`);
  }
}

/** Shared singleton used across the app. */
export const api = new ApiClient();
export default api;
