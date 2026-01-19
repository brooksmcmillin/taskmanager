# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in this project, please report it responsibly:

1. **Do NOT** open a public GitHub issue
2. Email the maintainers with details of the vulnerability
3. Include steps to reproduce, potential impact, and any suggested fixes
4. Allow reasonable time for a fix before public disclosure

## Security Measures

This project implements multiple layers of security:

### Authentication & Authorization

- **Session-based Auth**: Secure HTTP-only cookies with bcrypt password hashing
- **OAuth 2.0 with PKCE**: API access via OAuth with proof key for code exchange
- **Token Introspection**: Real-time token validation (RFC 7662)
- **Scope-based Access Control**: Fine-grained permissions via OAuth scopes
- **Device Authorization Grant**: RFC 8628 support for CLI/IoT devices

### Code Security

Automated security scanning via GitHub Actions:

- **CodeQL**: Static analysis for security vulnerabilities
- **ESLint Security**: JavaScript/TypeScript security linting
- **Bandit**: Python security linter
- **Trivy**: Vulnerability scanner for dependencies and Docker images
- **npm audit**: Check for known vulnerabilities in Node.js packages
- **pip-audit**: Check for known vulnerabilities in Python packages

### Secret Management

- **Environment Variables**: All credentials stored in `.env` files (gitignored)
- **Secret Detection**: Pre-commit hooks scan for accidentally committed secrets
- **No Hardcoded Credentials**: All authentication uses environment variables

### Docker Security

- **Minimal Base Images**: Python slim and Node.js slim images
- **Image Scanning**: Trivy scans for vulnerabilities in base images
- **Minimal Dependencies**: Only required packages installed

### Network Security

- **HTTPS/TLS**: Production deployment requires valid SSL certificates
- **CORS Configuration**: Properly configured cross-origin headers
- **Reverse Proxy**: Nginx handles SSL termination and request filtering

## Development Security

### Pre-commit Hooks

Install pre-commit hooks to catch security issues before committing:

```bash
pip install pre-commit
pre-commit install
```

This will automatically run:
- Secret detection (detect-secrets)
- Security linting (bandit for Python, eslint for JavaScript)
- Code formatting (ruff, prettier)
- Static analysis (mypy, TypeScript)

## Best Practices

### For Contributors

1. **Never commit secrets**: Use environment variables for all credentials
2. **Run pre-commit hooks**: Ensure `pre-commit install` is set up
3. **Review dependencies**: Check security of new dependencies before adding
4. **Update regularly**: Keep dependencies up to date
5. **Test OAuth flows**: Verify authentication works correctly

### For Deployers

1. **Use strong secrets**: Generate cryptographically secure client secrets
2. **Enable HTTPS**: Always use TLS in production
3. **Restrict CORS**: Configure appropriate CORS policies for your domain
4. **Monitor logs**: Watch for suspicious authentication patterns
5. **Update regularly**: Apply security patches promptly

## Known Limitations

**Educational Use**: This application is designed for educational and development purposes. While it implements security best practices, it has not undergone comprehensive security auditing for production environments handling highly sensitive data.

**MCP Token Storage**: The MCP auth server uses in-memory token storage by default. For production:
- Configure PostgreSQL-backed token storage
- Implement token revocation mechanisms

**Rate Limiting**: No built-in rate limiting. For production:
- Implement rate limiting at nginx level
- Add request throttling to prevent DoS

## Dependency Management

### Automated Updates

GitHub Actions runs security scans on every PR and weekly to detect vulnerable dependencies.

### Manual Updates

Check for updates regularly:

```bash
# Node.js (frontend)
cd services/frontend && npm audit

# Python (backend, MCP services, SDK)
cd services/backend && uv run pip-audit
cd services/mcp-auth && uv run pip-audit
cd services/mcp-resource && uv run pip-audit
```

## Compliance

This project follows:
- OAuth 2.0 (RFC 6749)
- OAuth 2.0 PKCE (RFC 7636)
- Token Introspection (RFC 7662)
- Dynamic Client Registration (RFC 7591)
- OAuth 2.0 Authorization Server Metadata (RFC 8414)
- Device Authorization Grant (RFC 8628)
- Resource Indicators for OAuth 2.0 (RFC 8707) - optional

## Security Checklist

Before deploying to production:

- [ ] All secrets in environment variables (not hardcoded)
- [ ] HTTPS enabled with valid certificates
- [ ] CORS configured for your specific domain
- [ ] OAuth client secrets are cryptographically secure
- [ ] Reverse proxy (nginx) properly configured
- [ ] Docker images scanned for vulnerabilities
- [ ] Dependencies updated to latest secure versions
- [ ] Monitoring and logging in place
- [ ] Backup and recovery plan established
- [ ] Security scanning in CI/CD pipeline
- [ ] Pre-commit hooks installed for all developers

## Contact

For security concerns, contact the project maintainers.
