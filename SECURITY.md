# Security Policy

Gela PM System is used in production at Gela Dairy Co. Please report security
problems privately so they can be fixed before they are discussed in public.

## Supported versions

Only the latest 2.4.x release is supported.

## Reporting a vulnerability

- Do **not** open a public issue.
- E-mail **MehrshadZiari79@gmail.com** with the version, the steps to reproduce
  and, if possible, the `error.log` from `%LOCALAPPDATA%\GelaDairy\PMSystem\`.
- You will get an answer within a few working days.

## Secrets

No passwords are stored in this repository. Database settings live in
`database/db_secrets.py`, which is git-ignored (template:
`database/db_secrets.example.py`). Installers built from this code contain
those settings and are therefore never attached to GitHub releases.
