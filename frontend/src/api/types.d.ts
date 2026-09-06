/**
 * DTOs returned by the Remarka API. Mirrors backend/app/schemas/*.py one-to-one.
 * Imported by TypeScript consumers; JS consumers get the same typing through JSDoc.
 */

export type UUID = string;
export type ISODateTime = string;
export type EntryType = 'quote' | 'note';
export type AIContextType = 'all_library' | 'current_book' | 'favorites';
export type Theme = 'system' | 'light' | 'dark';
export type PlanCode = 'free' | 'premium';
export type SortOrder = 'recent' | 'oldest' | 'title';

export interface ApiErrorEnvelope {
  error: { code: string; message: string; details?: unknown };
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  expires_at: ISODateTime;
  is_new_user: boolean;
}

export interface Profile {
  first_name: string | null;
  last_name: string | null;
  username: string | null;
  avatar_url: string | null;
  language_code: string | null;
}

export interface Preferences {
  theme: Theme;
  language: string | null;
}

export interface AIUsage {
  plan: PlanCode;
  used: number;
  limit: number;
  remaining: number;
  period_end: ISODateTime;
}

export interface Me {
  id: UUID;
  created_at: ISODateTime;
  onboarding_completed: boolean;
  profile: Profile;
  preferences: Preferences;
  plan: PlanCode;
  is_premium: boolean;
  ai_usage: AIUsage;
}

export interface Stats {
  books_count: number;
  quotes_count: number;
  notes_count: number;
  entries_count: number;
  favorites_count: number;
  tags_count: number;
}

export interface BookSearchItem {
  source: 'google_books' | 'open_library';
  source_id: string;
  title: string;
  subtitle: string | null;
  authors: string[];
  description: string | null;
  isbn_10: string | null;
  isbn_13: string | null;
  published_year: number | null;
  publisher: string | null;
  cover_url: string | null;
  categories: string[];
}

export interface Book {
  id: UUID;
  title: string;
  subtitle: string | null;
  authors: string[];
  description: string | null;
  isbn_10: string | null;
  isbn_13: string | null;
  published_year: number | null;
  publisher: string | null;
  cover_url: string | null;
  source: string;
}

export interface Category {
  id: UUID;
  name: string;
}

export interface UserBook {
  id: UUID;
  book: Book;
  category: Category | null;
  is_favorite: boolean;
  entries_count: number;
  quotes_count: number;
  notes_count: number;
  created_at: ISODateTime;
  updated_at: ISODateTime;
}

export interface AddBookFromCatalog {
  source: string;
  source_id: string;
  title: string;
  subtitle?: string | null;
  authors?: string[];
  description?: string | null;
  isbn_10?: string | null;
  isbn_13?: string | null;
  published_year?: number | null;
  publisher?: string | null;
  cover_url?: string | null;
  category?: string | null;
}

export interface ManualBookCreate {
  title: string;
  authors?: string[];
  description?: string | null;
  cover_url?: string | null;
  published_year?: number | null;
  category?: string | null;
}

export interface Tag {
  id: UUID;
  name: string;
}

export interface TagWithCount extends Tag {
  entries_count: number;
}

export interface EntryBook {
  user_book_id: UUID;
  book_id: UUID;
  title: string;
  authors: string[];
  cover_url: string | null;
}

export interface Entry {
  id: UUID;
  user_book_id: UUID;
  type: EntryType;
  content: string;
  personal_note: string | null;
  chapter: string | null;
  page: string | null;
  is_favorite: boolean;
  tags: Tag[];
  book: EntryBook | null;
  created_at: ISODateTime;
  updated_at: ISODateTime;
}

export interface EntryCreate {
  type: EntryType;
  content: string;
  personal_note?: string | null;
  chapter?: string | null;
  page?: string | null;
  is_favorite?: boolean;
  tags?: string[];
}

export type EntryUpdate = Partial<Omit<EntryCreate, 'type'>>;

export interface SearchResults {
  query: string;
  books: UserBook[];
  quotes: Entry[];
  notes: Entry[];
  total: number;
}

export interface AISource {
  entry_id: UUID;
  user_book_id: UUID;
  book_id: UUID;
  book_title: string;
  book_cover_url: string | null;
  entry_type: EntryType;
  chapter: string | null;
  page: string | null;
  snippet: string;
  relevance_score: number | null;
}

export interface AIMessage {
  id: UUID;
  role: 'user' | 'assistant';
  content: string;
  sources: AISource[];
  created_at: ISODateTime;
}

export interface AIConversation {
  id: UUID;
  title: string;
  context_type: AIContextType;
  context_user_book_id: UUID | null;
  created_at: ISODateTime;
  updated_at: ISODateTime;
  last_message: string | null;
  messages_count: number;
}

export interface AIConversationDetail extends AIConversation {
  messages: AIMessage[];
}

export interface AIAskResponse {
  conversation_id: UUID;
  message: AIMessage;
  status: 'ok' | 'not_enough_context';
  usage: AIUsage;
}

export interface PaymentProvider {
  code: 'telegram_stars' | 'yookassa' | 'platega' | 'cryptobot';
  enabled: boolean;
  currency: string;
}

export interface BillingStatus {
  plan: PlanCode;
  is_premium: boolean;
  status: string;
  expires_at: ISODateTime | null;
  ai_limit: number;
  ai_used: number;
  ai_remaining: number;
  period_end: ISODateTime;
  premium_price_stars: number;
}

export interface Invoice {
  payment_id: string;
  provider: string;
  payload: string;
  amount: number;
  currency: string;
  invoice_url: string | null;
  status: 'pending' | 'succeeded' | 'failed' | 'canceled';
}

export interface PaymentStatus {
  payment_id: string;
  status: string;
  plan: PlanCode;
  is_premium: boolean;
}

export interface LegalDocument {
  slug: string;
  title: string;
  updated_at: string | null;
  is_placeholder: boolean;
  content: string;
}
