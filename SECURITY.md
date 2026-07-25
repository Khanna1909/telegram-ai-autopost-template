# Security

Never place API keys, bot tokens, channel credentials or personal data in files.
Use GitHub Actions Secrets.

The repository is safe by default:

- `DRY_RUN=true`;
- `TELEGRAM_ENABLED=false`;
- every live run also requires `confirm_live=true`;
- the test workflow uses empty credentials;
- `safe-check` never calls KIE or Telegram;
- no built-in cron schedule is enabled.

If a secret is exposed, revoke it at the provider immediately and create a new
one. Do not open a public issue containing tokens, logs with credentials or
private channel data.

