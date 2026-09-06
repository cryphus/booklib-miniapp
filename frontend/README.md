# Remarka frontend

`src/api/` is ready and framework-agnostic:

| File | What it is |
|---|---|
| `client.js` | the single API client — base URL, bearer token, timeouts, JSON, unified error envelope, one method per backend endpoint |
| `telegram.js` | Telegram WebApp bootstrap: `ready()`/`expand()`, theme variables, safe area, BackButton, haptics, `openInvoice()`, and a browser fallback that uses the dev login |
| `types.d.ts` | TypeScript definitions for every API DTO |

Nothing here renders UI: the Mini App design is the source of truth and its screens get
wired to these modules.

```js
import { api, ApiError, errorMessage } from './src/api/client.js';
import { initTelegram, authenticate, haptic, openInvoice } from './src/api/telegram.js';

initTelegram();
await authenticate();                 // Telegram initData, or dev login in a browser
const library = await api.getLibrary({ page: 1, page_size: 20 });
```

Point the client at the backend with `window.REMARKA_API_URL` (plain HTML) or
`VITE_API_URL` (bundler build). Default: `http://localhost:8000/api/v1`.
