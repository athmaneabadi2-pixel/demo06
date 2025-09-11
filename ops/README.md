\# Ops scripts — demo06



\## Prérequis

set "BASE=https://demo06.onrender.com"

set "TOKEN=dev-123"   REM = même valeur que INTERNAL\_TOKEN côté Render





\## Smoke (prod)

ops\\smoke\_prod.bat %BASE% %TOKEN%







\## Diagnostic (prod)

ops\\diag\_prod.bat %BASE% %TOKEN%







\## Valider les profils

ops\\profile\_check.bat







\## Notes

\- Render Free : possible cold-start ⇒ si `HEALTH 502/504`, réessaie après ~30s.

\- Si `SEND 401/403` : `%TOKEN%` ≠ `INTERNAL\_TOKEN` (Render).

\- Si `WEBHOOK 401/403` : `VERIFY\_TWILIO\_SIGNATURE=true` sans signature (test local) — mets `false` pour tester.



