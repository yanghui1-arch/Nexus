# Nexus
Nexus: Next automatic enterprise coding agent system with 24*7. Supports python and React coding.

## User login and billing

Nexus currently supports GitHub OAuth login only. Create a GitHub OAuth App, set its callback URL to the web login page (for example `https://your-web-domain/login`), then configure:

- `NEXUS_GITHUB_OAUTH_CLIENT_ID`
- `NEXUS_GITHUB_OAUTH_CLIENT_SECRET`
- `NEXUS_JWT_SECRET` (use a high-entropy secret, at least 32 characters)
- `NEXUS_JWT_ALGORITHM` (defaults to `HS256`)
- `NEXUS_JWT_EXPIRATION_HOURS` (defaults to `168`)

The frontend sends the login page URL as GitHub's `redirect_uri`; after GitHub redirects back with `code`, the backend exchanges it for the GitHub user, creates the user if needed, and returns a bearer token. User balances are stored as CNY `Numeric(19, 2)` values. Agent monthly prices are Tela `￥5500.00` and Sophie `￥6000.00`.
