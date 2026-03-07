Sanitise a config file before committing, stripping all PII, telemetry, and sensitive data.

The user will provide a file path. If not, ask which file to sanitise.

## Process

1. Read the file and identify all sensitive data:
   - **Telemetry/analytics**: MSAppCenter IDs, crash reporting tokens, session history, device fingerprints
   - **Personal URLs**: OAuth callback URLs with tenant IDs or user IDs, `lastUrl` fields with personal browsing history
   - **Licence keys**: Replace with `PLACEHOLDER` or `<YOUR_KEY_HERE>`
   - **Personal paths**: `/Users/username/...` paths, recently opened files, recent clone directories
   - **Device info**: Hardware model, OS version, screen size, locale-specific data
   - **Email addresses**: Replace with `user@example.com`
   - **IP addresses**: Replace with `0.0.0.0` or remove

2. For each finding, show the user what will be changed:
   ```
   Line 42: "email": "warren@example.com" → "email": "user@example.com"
   Line 87: MSAppCenterInstallId → REMOVED
   ```

3. Apply the changes after user confirmation.

4. Verify the sanitised file is still valid (parse JSON/plist/YAML).

## Common file types
- **plist** files: Use `plutil -remove` for keys, `plutil -replace` for values
- **JSON** files: Edit directly
- **YAML** files: Edit directly

## Examples of things to strip
- `MSAppCenterInstallId`, `MSAppCenterSessionIdHistory`, `MSAppCenterPastDevices`
- `NSOSPLastRootDirectory`, `recentCloneDirectories`
- `lastUrl` fields (replace with `homeUrl` values)
- Paddle/licence activation tokens
- Corporate SSO URLs with tenant/user identifiers
