# White Labeling and Customization Guide

## SambaNova Agents

---

## Table of Contents

- [Overview](#overview)
- [Section 1: Getting Your Agents Fork Set Up](#section-1-getting-your-agents-fork)
- [Section 2: Documentation Branding](#section-2-documentation-branding)
- [Section 3: Frontend Branding](#section-3-frontend-branding)
- [Section 4: LLM Provider and Base URL Configuration](#section-4-llm-provider-and-base-url-configuration)
- [Section 5: Auth0 Standardization](#section-5-auth0-standardization)
- [Section 6: Admin Panel and User Keys](#section-6-admin-panel-and-user-keys)
- [Section 7: Legal and Policy Pages](#section-7-legal-and-policy-pages)
- [Section 8: Deployment Overview](#section-8-deployment-overview)
- [Section 9: Verification Checklist](#section-9-verification-checklist)
- [Section 10: Troubleshooting](#section-10-troubleshooting)
- [Additional Resources](#additional-resources)
- [Document Changelog](#document-changelog)
- [License & Attribution](#license--attribution)

---

## Overview

This guide provides comprehensive instructions for customizing and white labeling the SambaNova Agents application for your deployment. As a SambaManaged customer with your own branded infrastructure, you can adapt these resources to:

- Replace SambaNova branding with your branding (`<Custx>`)
- Configure the application to use your SambaManaged URL (for example, `https://cloud.<custx_domain>/v1`)
- Customize documentation, UI, and marketing callouts
- Use your own Auth0 tenant

### What This Guide Covers

- Documentation and API spec customization
- Frontend branding (logos, text, colors, marketing callouts)
- LLM provider base URL and model configuration
- Auth0 configuration
- Admin panel and API key behavior
- Deployment and verification

### Important Internal Naming Note

This guide keeps internal provider IDs and headers as `sambanova` for compatibility (for example, `sambanova` provider ID and `X-SambaNova-Key` header). Update display labels and external URLs to `<Custx>`, but do not rename internal IDs unless you are prepared for a deep refactor.

### Placeholder Conventions

Use these placeholders consistently throughout your fork:

- `<Custx>`: Your company or product name
- `<custx_org>`: Your GitHub org or repo owner
- `<custx_domain>`: Your primary domain
- `<custx_cloud_url>`: Your cloud API base URL (include `/v1` if your API requires it)
- `<custx_app_url>`: Your public web app URL
- `<custx_privacy_url>`: Your privacy policy URL
- `<custx_terms_url>`: Your terms of service URL
- `<custx_docs_url>`: Your public docs or API reference URL
- `<custx_support_email>`: Your support or contact email
- `<auth0_domain>`: Your Auth0 tenant domain
- `<auth0_client_id>`: Your Auth0 client ID
- `<auth0_audience>`: Your Auth0 API audience (if you use one)

### Placeholder Review Checklist

- Confirm `<custx_cloud_url>` includes `/v1` if your OpenAI-compatible endpoints require it.
- Confirm `<custx_app_url>` is the exact public URL your users will access.
- Confirm `<custx_privacy_url>` and `<custx_terms_url>` are final legal URLs.
- Confirm `<custx_docs_url>` matches your public documentation location.
- Confirm `<custx_support_email>` is monitored and used in API spec metadata.

---

## Section 1: Getting Your Agents Fork Set Up

- Fork the [SambaNova Agents repository](https://github.com/sambanova/agents).
- Clone your fork:

```bash
git clone https://github.com/<custx_org>/agents.git
cd agents
```

- Create a white-label branch:

```bash
git checkout -b whitelabel-customization
```

Optional: if you were given a SambaManaged branch, branch from it instead:

```bash
git fetch origin sambamanaged
git checkout -b whitelabel-customization origin/sambamanaged
```

---

## Section 2: Documentation Branding

### 2.1 Files to Update

- `agents/README.md`
- `agents/CONTRIBUTING.md`
- `agents/chat-sambanova-agent-api-spec.yaml`

### 2.2 Replace Branding and Links

Find and replace the following patterns (be careful around legal and attribution text):

| Original | Replace with (example) | Files |
|----------|------------------------|-------|
| `SambaNova` | `<Custx>` | Docs and UI text (carefully) |
| `https://sambanova.ai/` | `https://<custx_domain>/` | Docs, UI links |
| `https://cloud.sambanova.ai/` | `<custx_cloud_url>` | Docs, UI links |
| `https://aiskagents.cloud.snova.ai/` | `<custx_app_url>` | Docs |
| `https://community.sambanova.ai/` | `https://community.<custx_domain>/` | UI settings links |
| `info@sambanova.ai` | `<custx_support_email>` | API spec |
| `https://docs.sambanova.ai/cloud/api-reference/overview` | `<custx_docs_url>` | API spec |

### 2.2.1 README Logo URL

The README currently references a SambaNova-hosted logo path. The bulk replace script will only swap the domain, which can leave a broken image. Update the logo link manually before running the script.

File: `agents/README.md`

Example replacement:

```markdown
![<Custx> Agents Logo](./frontend/sales-agent-crew/public/Images/logo-nsai.svg)
```

If you prefer a hosted logo, replace the URL with your own CDN location.

### 2.3 API Spec Metadata (OpenAPI)

Update the API metadata to show your `<Custx>` branding:

File: `agents/chat-sambanova-agent-api-spec.yaml`

Example edits:

```yaml
info:
  title: <Custx> Agents Service
  description: Service for <Custx> Agents
  termsOfService: <custx_terms_url>
  contact:
    email: <custx_support_email>
    name: <Custx> Support
servers:
  - url: <custx_cloud_url>
```

### 2.4 Bulk Find/Replace (Optional, Docs Only)

This section targets documentation files only. It does not touch source code.

Audit:

```bash
rg -n "SambaNova|sambanova.ai|cloud.snova.ai|aiskagents.cloud.snova.ai|community.sambanova.ai|chat.sambanova.ai|info@sambanova.ai|docs.sambanova.ai" \
  README.md \
  CONTRIBUTING.md \
  chat-sambanova-agent-api-spec.yaml
```

Optional batch replace (docs only):

```bash
python - <<'PY'
from pathlib import Path

replacements = {
    "SambaNova": "<Custx>",
    "https://sambanova.ai/": "https://<custx_domain>/",
    "https://cloud.sambanova.ai/": "<custx_cloud_url>",
    "https://aiskagents.cloud.snova.ai/": "<custx_app_url>",
    "https://community.sambanova.ai/": "https://community.<custx_domain>/",
    "https://chat.sambanova.ai/": "<custx_app_url>",
    "info@sambanova.ai": "<custx_support_email>",
    "https://docs.sambanova.ai/cloud/api-reference/overview": "<custx_docs_url>",
}

targets = [
    Path("README.md"),
    Path("CONTRIBUTING.md"),
    Path("chat-sambanova-agent-api-spec.yaml"),
]

for path in targets:
    text = path.read_text(encoding="utf-8")
    new_text = text
    for old, new in replacements.items():
        new_text = new_text.replace(old, new)
    if new_text != text:
        path.write_text(new_text, encoding="utf-8")
        print(f"updated {path}")
PY
```

Notes:

- Legal/attribution text should be reviewed manually instead of auto-replacing.

---

## Section 3: Frontend Branding

### 3.1 Logo, Favicon, and Media Replacement

Replace the following assets with `<Custx>` branding:

- `agents/frontend/sales-agent-crew/public/Images/logo-nsai.svg`
- `agents/frontend/sales-agent-crew/public/Images/logo-sai.png`
- `agents/frontend/sales-agent-crew/public/Images/logo-icon.png`
- `agents/frontend/sales-agent-crew/public/Images/logo-icon.svg`
- `agents/frontend/sales-agent-crew/public/Images/agent-screen-recording.webm`
- `agents/frontend/sales-agent-crew/public/Images/screen.jpg`
- `agents/frontend/sales-agent-crew/public/logo-icon.svg`
- `agents/frontend/sales-agent-crew/public/logo-sai.png`

Keeping the filenames the same avoids code changes.

Example (copy your logo assets into place):

```bash
cp /path/to/<custx-logo>.svg agents/frontend/sales-agent-crew/public/Images/logo-nsai.svg
cp /path/to/<custx-icon>.svg agents/frontend/sales-agent-crew/public/Images/logo-icon.svg
cp /path/to/<custx-favicon>.ico agents/frontend/sales-agent-crew/public/favicon.ico
```

### 3.2 Page Title and Metadata

File: `agents/frontend/sales-agent-crew/index.html`

Example:

```html
<link rel="icon" href="/Images/logo-icon.svg">
<title><Custx> Agents</title>
```

### 3.3 Header and Login Branding

In files:

- `agents/frontend/sales-agent-crew/src/components/Header.vue`
- `agents/frontend/sales-agent-crew/src/views/LoginPage.vue`

Search for SambaNova, and replace with your naming convention and links

Example edits:

```html
<img src="/Images/logo-nsai.svg" alt="<Custx> Logo" class="h-8" />
<span class="text-base sm:text-lg font-semibold text-gray-500"><Custx> Agents</span>
```

### 3.4 Marketing Callouts and UI Copy

Files:

- `agents/frontend/sales-agent-crew/src/components/ChatMain/Fastest.vue`
- `agents/frontend/sales-agent-crew/src/components/ChatMain/MaximizeBox.vue`
- `agents/frontend/sales-agent-crew/src/components/ChatMain/ChatBubble.vue`
- `agents/frontend/sales-agent-crew/src/components/ChatMain/ChatBubbleInter.vue`
- `agents/frontend/sales-agent-crew/src/components/ChatMain/ChatLoaderBubble.vue`

Examples to update:

- "Switch to Llama 4 - Maverick on SambaNova..."
- "Experience faster speeds ... thanks to SambaNova RDUs..."
- "Generated with SambaNova Agents"

Replace these with `<Custx>` marketing copy or remove if not relevant.

### 3.5 Settings and Provider Labels

Files:

- `agents/frontend/sales-agent-crew/src/components/SettingsModal.vue`
- `agents/frontend/sales-agent-crew/src/components/AdminPanelSettings.vue`
- `agents/frontend/sales-agent-crew/src/components/Settings/CleanConnectorsTab.vue`

#### What to change (safe)

Only update user-visible strings and labels. Keep internal provider IDs and key names unchanged.

Safe examples:

- UI labels and headings:

```html
SambaNova API Key
```

becomes:

```html
<Custx> API Key
```

- Provider display labels (label only):

```js
{ label: 'SambaNova', value: 'sambanova' }
```

and

```js
<option value="sambanova">SambaNova Compatible</option>
```

becomes:

```js
{ label: '<Custx>', value: 'sambanova' }
```
and

```js
<option value="sambanova"><custx> Compatible</option>
```

- Provider name display helper (Admin Panel):

```js
const names = {
  sambanova: '<Custx>',
  fireworks: 'Fireworks AI',
  together: 'Together AI'
}
```

- Help links:

```html
href="https://cloud.sambanova.ai/"
```

becomes:

```html
href="<custx_cloud_url>"
```

#### What not to change (keep internal IDs)

Do not rename internal provider IDs, localStorage keys, request headers, or API fields.

Examples that must stay as-is:

```js
localStorage.getItem(`sambanova_key_${userId}`)
provider === 'sambanova'
value: 'sambanova'
'X-SambaNova-Key'
```

These identifiers are wired end-to-end (frontend → backend → Redis) and changing them will break saved keys, defaults, and API calls.

#### Quick audit (safe vs unsafe replacements)

To update user-visible strings only:

```bash
rg -n "SambaNova" frontend/sales-agent-crew/src/components/SettingsModal.vue \
  frontend/sales-agent-crew/src/components/AdminPanelSettings.vue \
  frontend/sales-agent-crew/src/components/Settings/CleanConnectorsTab.vue
```

To verify you did not change internal IDs:

```bash
rg -n "sambanova_key|X-SambaNova-Key|provider === 'sambanova'|value: 'sambanova'|sambanova\"" \
  frontend/sales-agent-crew/src
```

### 3.6 Colors, Fonts, and Theme

Files:

- `agents/frontend/sales-agent-crew/tailwind.config.js`
- `agents/frontend/sales-agent-crew/src/style.css`
- `agents/frontend/sales-agent-crew/src/assets/base.css`
- `agents/frontend/sales-agent-crew/src/components/ChatMain/SelectProvider.vue`
- `agents/frontend/sales-agent-crew/src/views/MainLayout.vue`

#### 3.6.1 Update the Tailwind brand palette

Example (Tailwind palette in `tailwind.config.js`):

```js
extend: {
  colors: {
    primary: {
      500: "<custx_primary_color>",
      700: "<custx_primary_color_dark>"
    }
  }
}
```

Also update the existing brand tokens so UI classes like `bg-primary-brandColor` and `text-primary-brandTextPrimary` pick up your colors:

```js
primary: {
  brandColor: "<custx_primary_color>",
  brandPrimaryColor: "<custx_primary_color>",
  brandBorder: "<custx_border_color>",
  brandTextPrimary: "<custx_text_primary>",
  brandTextSecondary: "<custx_text_secondary>",
  bodyBg: "<custx_page_bg>"
}
```

#### 3.6.2 Replace hardcoded Tailwind colors

Some components still use built-in Tailwind colors like `indigo-*` and `purple-*`. These do not change when you update the brand palette. Replace them with your `primary-*` tokens.

Quick audit:

```bash
rg -n "indigo-|purple-|blue-" frontend/sales-agent-crew/src
```

Common fixes:

- Login CTA button and links:
  - `agents/frontend/sales-agent-crew/src/views/LoginPage.vue`
  - Replace `bg-indigo-600`, `hover:bg-indigo-700`, `focus:ring-indigo-500`, `text-indigo-600`
  - Use `bg-primary-brandColor`, `hover:bg-primary-700`, `focus:ring-primary-500`, `text-primary-brandColor`

- Header user badge:
  - `agents/frontend/sales-agent-crew/src/components/Header.vue`
  - Replace `ring-indigo-100`, `focus:ring-indigo-500`, `text-indigo-600`, `bg-indigo-100`
  - Use `primary` equivalents

- Destructive delete button color:
  - `agents/frontend/sales-agent-crew/src/components/SettingsModal.vue`
  - If you want a destructive color, use Tailwind `red-*` classes.
  - If you want brand color, keep `bg-primary-brandColor` and update the palette in `tailwind.config.js`.

- Sidebar buttons 
    - `agents/frontend/sales-agent-crew/src/components/ChatSidebar.vue`
    - Replace `bg-purple-50`, `text-purple-700`, `bg-purple-100`
    - Use `primary` equivalents

#### 3.6.3 Validate changes

- Login page button and "Continue" links use your `<Custx>` colors.
- Delete/confirm actions use your desired brand or destructive color.
- No remaining `indigo-` or `purple-` classes unless intentionally kept.

---

## Section 4: LLM Provider and Base URL Configuration

### 4.1 Default Provider Configuration (YAML)

File: `agents/backend/src/agents/config/llm_config.yaml`

Update the provider name and base URL, but keep the provider ID as `sambanova`:

```yaml
providers:
  sambanova:
    name: "<Custx>"
    base_url: "<custx_cloud_url>"
default_provider: sambanova
```

If you want to change default models for tasks, update `task_models` in the same file.

### 4.2 Admin Panel Provider Metadata

File: `agents/backend/src/agents/api/routers/admin.py`

Update the provider metadata shown in the admin UI:

```python
"sambanova": {
    "name": "<Custx>",
    "url": "<custx_cloud_url>",
    "description": "Get your API key from <Custx> console"
}
```


### 4.3 Model Registry URLs

File: `agents/backend/src/agents/registry/model_config.json`

Update `url` and `long_url` fields:

```json
{
  "url": "<custx_cloud_url>",
  "long_url": "<custx_cloud_url>/chat/completions"
}
```

### 4.4 LLM Config Manager Fallback

File: `agents/backend/src/agents/config/llm_config_manager.py`

Update the fallback base URL in `DEFAULT_CONFIG` so the app does not fall back to SambaNova if the YAML config is missing:

```python
"base_url": "<custx_cloud_url>"
```

### 4.5 CrewAI Default Base URLs

File: `agents/backend/src/agents/utils/llm_provider.py`

Update the default base URLs:

```python
DEFAULT_BASE_URLS = {
    "sambanova": "<custx_cloud_url>",
    "fireworks": "https://api.fireworks.ai/inference/v1",
    "together": "https://api.together.xyz/v1"
}
```

### 4.6 Hard-Coded Endpoints

Update explicit endpoints in the following files:

- `agents/backend/src/agents/services/query_router_service.py`
- `agents/backend/src/agents/tools/competitor_llm_tool.py`
- `agents/backend/src/agents/components/compound/xml_agent.py`

Example:

```python
self.api_url = "<custx_cloud_url>/chat/completions"
```

If `<custx_cloud_url>` already includes `/v1`, this resolves to:

```
https://cloud.<custx_domain>/v1/chat/completions
```

#### 4.6.1 Audit for Remaining SambaNova API URLs

Run this after completing Section 4 to catch any leftover SambaNova endpoints:

```bash
rg -n "api\\.sambanova\\.ai|cloud\\.sambanova\\.ai|chat\\.sambanova\\.ai" agents
```

### 4.7 Audio Reasoning Endpoints

Update audio reasoning URLs (if voice features are enabled):

- `agents/frontend/sales-agent-crew/src/components/SearchSection.vue`
- `agents/frontend/sales-agent-crew/src/components/ChatMain/ChatView.vue`

Example:

```js
"<custx_cloud_url>/audio/reasoning"
```

### 4.8 Provider Headers (Do Not Rename)

Keep internal header and key names for compatibility:

- `X-SambaNova-Key` in `agents/frontend/sales-agent-crew/src/services/api.js`
- `sambanova_key` storage fields in backend services

Update only the UI display text for these keys.

---

## Section 5: Auth0 Standardization

### 5.1 Frontend Environment Variables

File: `agents/frontend/sales-agent-crew/.env.example`

```bash
VITE_AUTH0_DOMAIN=<auth0_domain>
VITE_AUTH0_CLIENT_ID=<auth0_client_id>
VITE_AUTH0_SCOPES=openid profile email
```

### 5.2 Backend Environment Variables

File: `agents/backend/.env.example`

```bash
AUTH0_DOMAIN=<auth0_domain>
```

`AUTH0_DOMAIN` is required. The backend validates tokens via Auth0's `/userinfo` endpoint and does not currently read `AUTH0_AUDIENCE`. Only set `AUTH0_AUDIENCE` if you add audience-based checks later.

Auth0 is enforced in:

- `agents/backend/src/agents/auth/auth0_config.py`
- `agents/frontend/sales-agent-crew/src/main.js`

### 5.3 Auth0 Callback URLs

Auth0 uses callback URLs to return users to your app after login. The Agents frontend sets:

- Local dev: `redirect_uri = http://localhost:5173`
- Non-local: `redirect_uri = <custx_app_url>/callback`

You must register both in your Auth0 Application settings so the redirect is accepted.

- Allowed Callback URLs:
  - `<custx_app_url>`
  - `<custx_app_url>/callback`
  - `http://localhost:5173`
- Allowed Logout URLs:
  - `<custx_app_url>`
  - `http://localhost:5173`

Notes:

- If you use a staging domain, add it to both lists as well.
- For SPA routing, make sure your frontend server rewrites `/callback` to `index.html`.
- If you use Auth0 silent auth, also add `<custx_app_url>` to Allowed Web Origins.

---

## Section 6: Admin Panel and User Keys

### 6.1 Enable the Admin Panel

Why enable it:

- Lets users switch models and providers without a code change.
- Lets your users use new available or custom models without redeploying the app.

What it enables:

- Adds an Admin tab in Settings for model and provider configuration.
- Allows adding custom providers and updating default model selections.
- Saves provider config per user in Redis (update `llm_config.yaml` for org-wide defaults)

Backend:

```bash
# agents/backend/.env.example
SHOW_ADMIN_PANEL=true
```

Frontend:

```bash
# agents/frontend/sales-agent-crew/.env.example
VITE_SHOW_ADMIN_PANEL=true
```

### 6.2 User-Provided API Keys

Control user key behavior:

- `ENABLE_USER_KEYS` in `agents/backend/.env.example`
- `VITE_ENABLE_USER_KEYS` in `agents/frontend/sales-agent-crew/.env.example`

Behavior is enforced in:

- `agents/backend/src/agents/api/websocket_manager.py`

Reminder: you must supply your own enterprise keys for add-on services used by the app (for example Daytona, Tavily, Exa, Serper, Hume, and LangSmith). See the "Prerequisites" and "Environment variables setup" sections in `agents/README.md` for the full list and context.

Also review the example env files for the full variable list:

- `agents/backend/.env.example`
- `agents/frontend/sales-agent-crew/.env.example`

### 6.3 Redis Master Salt (Required for Encryption)

File: `agents/backend/.env.example`

Generate a value:

```bash
python - <<'PY'
import os, base64
print(base64.b64encode(os.urandom(32)).decode())
PY
```

Set:

```bash
REDIS_MASTER_SALT=<base64_value>
```

---

## Section 7: Legal and Policy Pages

Update legal text and links with `<Custx>` language:

- `agents/frontend/sales-agent-crew/src/views/TermsOfService.vue`
- `agents/frontend/sales-agent-crew/src/views/LoginPage.vue`

Recommended approach:

- Replace the entire Terms of Service text with `<Custx>` legal copy.
- Update Privacy Policy links to `<custx_privacy_url>`.

Example (Login footer):

```html
<a href="<custx_terms_url>">Terms Of Service</a>
<a href="<custx_privacy_url>" target="_blank">Privacy Policy</a>
```

---

## Section 8: Deployment Overview

### 8.1 Docker Compose

File: `agents/docker-compose.yml`

- Update domain-related environment variables.
- Update certificate mount paths if needed.
- Ensure `ALLOWED_ORIGINS` is set to your frontend domain.

Example:

```yaml
environment:
  - ALLOWED_ORIGINS=<custx_app_url>
```

### 8.2 Helm / Kubernetes

Files:

- `agents/helm/values.yaml`
- `agents/helm/aiskagents/values.yaml`
- `agents/helm/aiskagents/values.dev.yaml`
- `agents/helm/aiskagents/values.prod.yaml`

Update ingress hosts and TLS secrets:

```yaml
ingress:
  host: <custx_app_url>
  tls:
    secretName: <custx_tls_secret>
```

Replace any `*.cloud.snova.ai` or `chat.sambanova.ai` hosts with `<custx_app_url>` equivalents.

---

## Section 9: Verification Checklist

- [ ] Branding updated across login, header, and chat UI
- [ ] `<Custx>` logos, favicon, and demo media display correctly
- [ ] Auth0 login works with your tenant
- [ ] API base URL points to `<custx_cloud_url>`
- [ ] Audio reasoning endpoint works (if enabled)
- [ ] Admin panel visible when enabled
- [ ] Legal links point to `<custx_domain>` resources

Quick audit:

```bash
rg -n "SambaNova|sambanova.ai|cloud.snova.ai|aiskagents.cloud.snova.ai|community.sambanova.ai|chat.sambanova.ai" agents
```

---

## Section 10: Troubleshooting

### Admin Panel Not Showing

- Confirm `SHOW_ADMIN_PANEL=true` and `VITE_SHOW_ADMIN_PANEL=true`
- Restart backend and frontend after environment changes

### Auth0 Errors

- Check `VITE_AUTH0_DOMAIN`, `VITE_AUTH0_CLIENT_ID`, and `AUTH0_DOMAIN`
- Verify allowed callback URLs in your Auth0 app settings

### Provider Base URL Issues

- Confirm `<custx_cloud_url>` is used in `llm_config.yaml`
- Remove any remaining `https://api.sambanova.ai/v1` references

### Failed to Load Saved Keys (Settings Modal)

- This usually happens when internal IDs or localStorage keys were renamed.
- Verify that `sambanova_key`, `X-SambaNova-Key`, and `provider === 'sambanova'` are unchanged.
- Revert any replacements that modified `sambanova` inside code identifiers.

### Provider Label Still Shows "SambaNova"

- Update display labels (not IDs) in:
  - `agents/frontend/sales-agent-crew/src/views/MainLayout.vue`
  - `agents/frontend/sales-agent-crew/src/components/ChatMain/SelectProvider.vue`
  - `agents/frontend/sales-agent-crew/src/components/AdminPanelSettings.vue`
- Keep `value: 'sambanova'` and `default_provider: sambanova` unchanged.

---

## Additional Resources

- Agents repo: `https://github.com/sambanova/agents`
- Auth0 docs: `https://auth0.com/docs`

---

## Document Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-01-16 | Initial release |

---

## License & Attribution

This guide assumes the underlying codebase remains under its original license. Preserve license and attribution requirements as required by the SambaNova Agents repository.
