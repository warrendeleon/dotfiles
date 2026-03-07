Scan all staged files for secrets, PII, and sensitive data before committing.

## What to scan for

### Secrets
- API keys, tokens, passwords, licence keys
- Private SSH keys (`id_rsa`, `id_ed25519`, `*.pem`, `*.key`)
- Certificates and keystores (`*.p12`, `*.pfx`, `*.keystore`)
- Database connection strings with credentials
- Bearer tokens, `sk-` prefixed keys, `pk_` prefixed keys

### PII (Personally Identifiable Information)
- Email addresses (replace with `user@example.com` or placeholders)
- Phone numbers, physical addresses
- Corporate tenant IDs, user OIDs, OAuth URLs with personal identifiers
- Device fingerprints, hardware IDs, telemetry data (e.g. MSAppCenter)
- IP addresses (internal or personal)
- Browser history, `lastUrl` fields, recently opened file paths

## Process

1. Run these checks against staged files:

```bash
# Check for secrets
git diff --cached | grep -iE "api.key|secret|token|password|Bearer|sk-|pk_|PRIVATE KEY" && echo "⚠️ SECRETS FOUND" || echo "✅ No secrets"

# Check for PII (emails, IPs)
git diff --cached | grep -iE "@[a-z]+\.(com|co\.uk|org|net|io)|[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}" && echo "⚠️ PII FOUND" || echo "✅ No PII"

# Check for AI references
git diff --cached | grep -i "claude\|anthropic\|AI generated\|co-authored-by" && echo "⚠️ AI REFS FOUND" || echo "✅ No AI references"
```

2. For each finding, determine if it's a real secret/PII or a false positive (e.g. `example.com` in docs is fine).
3. Report all real findings with file paths and line numbers.
4. **Do not proceed with the commit** if real secrets or PII are found. Fix them first.
