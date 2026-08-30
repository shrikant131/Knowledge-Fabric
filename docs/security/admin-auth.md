# Admin authentication

For local use, leave `ADMIN_API_KEY` unset and the product remains zero-configuration.

For a simple cloud POC, set `ADMIN_API_KEY` through the platform secret manager. Protected routes require:

`X-Admin-API-Key: <secret>`

This is a deployment guard, not a replacement for enterprise SSO/RBAC. For production, put the application behind OIDC/SSO and enforce identity/source ACLs before retrieval.
