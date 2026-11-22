# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability in PixelPilot, please report it responsibly rather than opening a public issue.

To report a vulnerability:
1. Contact the maintainer privately at `jyotiraditya.parmar@example.com` (or via GitHub Private Vulnerability Reporting).
2. Include a detailed description of the vulnerability, steps to reproduce, and any relevant logs or traces.
3. Please do not publish details of the vulnerability until a fix has been released.

## Security Practices in PixelPilot

- **Secret Redaction**: PixelPilot includes built-in redaction in `src/pixelpilot/config.py` (`redact_secrets`) that redacts configured API keys and typed password field values from execution logs and traces.
- **Allowed Hosts**: Navigation is strictly validated against an allowlist of permitted hosts (`localhost`, `127.0.0.1`, `::1`, and configured `base_url`).
- **No Untrusted Code Execution**: Story files use a constrained declarative markdown grammar parsed by the planner rather than executing arbitrary scripts.
