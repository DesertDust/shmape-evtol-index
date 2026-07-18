# Security

## Exposure model

The application is intentionally public and read-only. It provides no public create, update, delete, login, shell, debug, OpenAPI, or administrative endpoint. State changes happen only in scheduled in-cluster workers.

## Runtime controls

- non-root UID/GID 10001;
- read-only root filesystem;
- all Linux capabilities dropped;
- privilege escalation disabled;
- RuntimeDefault seccomp;
- service-account token automount disabled;
- explicit CPU/memory requests and limits;
- persistent data isolated in one namespace-scoped PVC;
- network policy allows cluster ingress to port 8000, DNS, and outbound HTTPS only;
- security headers include CSP, frame denial, MIME sniff prevention, strict referrer policy, and disabled camera/microphone/geolocation.

## Authentication and LDAP readiness

Public research routes need no identity. If administrative or subscriber features are added, authentication belongs at the shared edge through an LDAP-backed OIDC/forward-auth provider (for example Authentik or Authelia). The app must trust identity only from that authenticated proxy boundary, not arbitrary client-supplied headers. No LDAP bind password belongs in this repository.

## Messaging

Telegram and WhatsApp notifications are disabled. The application only exposes alert-ready data hooks. If enabled later, Telegram user/chat IDs and WhatsApp phone numbers must use explicit allowlists; an empty allowlist must deny all delivery. LDAP identity does not replace messaging-platform allowlists.

## Data and provider safety

- Provider symbols and intervals are allowlisted before URL construction.
- SEC/Yahoo responses are parsed as data and never executed.
- Discovery uses deterministic scoring and a high automatic-inclusion threshold.
- Lower-confidence discoveries are audited but not promoted.
- One provider failure cannot fabricate or erase stored data.
- API output contains no credentials or environment dumps.

## Reporting vulnerabilities

Do not file public issues containing credentials or private infrastructure details. Contact the repository owner privately.
