# Security Policy

## 🔐 Supported Versions

Currently supported versions with security updates:

| Version | Supported          |
| ------- | ------------------ |
| 1.x     | :white_check_mark: |

## 🚨 Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

If you discover a security vulnerability, please send an email to:

**security@novaroma-homelab.uk** (or create a private security advisory on GitHub)

### What to Include

Please include the following information:

- **Type of vulnerability** (e.g., SQL injection, XSS, authentication bypass)
- **Full path** of source file(s) related to the vulnerability
- **Location** of the affected code (tag/branch/commit or direct URL)
- **Step-by-step instructions** to reproduce the issue
- **Proof-of-concept** or exploit code (if possible)
- **Impact** of the vulnerability
- **Suggested fix** (if you have one)

### Response Timeline

- **24 hours**: Initial response acknowledging receipt
- **72 hours**: Initial assessment of severity
- **7 days**: Target for patch release (varies by severity)

## 🛡️ Security Best Practices

### For Deployments

1. **Environment Variables**
   - NEVER commit `.env` files to Git
   - Use strong `JWT_SECRET` (minimum 32 characters)
   - Rotate API keys regularly
   - Use different credentials for development/production

2. **Admin Account**
   - Change `BOOTSTRAP_ADMIN_PASSWORD` immediately after first deployment
   - Use strong, unique passwords
   - Limit admin account access

3. **Network Security**
   - Use Cloudflare Tunnel or VPN for production access
   - Don't expose port 8080 directly to the internet
   - Enable Cloudflare Access policies for additional protection
   - Use HTTPS only (Cloudflare provides SSL automatically)

4. **Database Security**
   - Regularly backup `data/gateway.db`
   - Limit file system access to database directory
   - Consider encrypted volumes for sensitive data

5. **Docker Security**
   - Keep Docker images updated
   - Don't run containers as root (already configured)
   - Use Docker secrets for sensitive data in production
   - Scan images for vulnerabilities

### For Developers

1. **Code Security**
   - Never hardcode credentials or API keys
   - Use environment variables for all secrets
   - Validate and sanitize all user inputs
   - Use parameterized queries (already done via SQLAlchemy)
   - Keep dependencies updated

2. **Authentication & Access Control**
   - JWT tokens expire after 1 hour
   - Passwords hashed with bcrypt + SHA-256 pre-hash
   - No plaintext passwords stored anywhere
   - Rate limiting on all authenticated endpoints (1000/hour for users, 5000/hour for admins)
   - Admin-only actions restricted: user deletion, viewing all rate limits
   - Input validation on all endpoints prevents injection attacks

3. **API Security**
   - All external API keys stored server-side only
   - Clients never receive or see provider API keys (OpenWeather, Geoapify, IPRegistry, Resend, search.ch, NASA, Open Library)
   - JWT required for all protected endpoints
   - Role-based access control (user/admin)
   - Rate limiting per API to protect external quotas
   - Input validation prevents malicious queries
   - Response headers include rate limit information

## 🔍 Known Security Considerations

### Rate Limiting

**Status**: ✅ IMPLEMENTED
**Implementation**: Per-user (1000/hour for users, 5000/hour for admins) and per-API rate limiting
**Protection**: Prevents abuse and protects external API quotas
**Details**: See RATE_LIMITING.md for comprehensive documentation

### Token Refresh

**Status**: Manual refresh required
**Risk**: Low - 1-hour token expiration is reasonable
**Recommendation**: Consider implementing refresh tokens for better UX

### Audit Logging

**Status**: ✅ IMPLEMENTED
**Implementation**: Comprehensive logging of user actions, rate limit violations, and API calls
**Features**:
- User authentication attempts logged
- Rate limit violations tracked with user ID and role
- API quota exceeded events logged
- Admin actions monitored
**Details**: All logs include timestamps, user IDs, and action details

## 📊 Security Updates

Security updates will be released as patch versions (e.g., 1.0.1, 1.0.2).

Check releases for security patches: https://github.com/JestingDart4369/ApiServer_Novaroma/releases

## 🏆 Security Hall of Fame

We appreciate security researchers who responsibly disclose vulnerabilities.

Contributors will be listed here (with permission):

- *No vulnerabilities reported yet*

## 📜 Compliance

### GDPR Considerations

This gateway stores:
- Usernames (personal data)
- Hashed passwords (not reversible)
- JWT tokens (temporary, 1-hour expiration)

If deploying in EU:
- Implement data deletion on user request
- Add privacy policy
- Log data access/modifications
- Obtain user consent for data processing

### API Key Security

All third-party API keys are:
- Stored server-side in `.env` (gitignored)
- Never transmitted to clients
- Never logged in plaintext
- Rotatable without client changes
- Protected by rate limiting to prevent quota exhaustion
- Each API has independent rate limit (NASA: 900/hour, OpenWeather: 3000/hour, etc.)

### Input Validation

All endpoints implement comprehensive input validation:
- Required parameters checked for presence
- String inputs sanitized to prevent injection
- Numeric parameters validated for range
- Date formats validated before external API calls
- Query parameters length-limited
- Email addresses validated for format
- ISBN/ID formats validated for book searches

## 📞 Contact

For security concerns: **security@novaroma-homelab.uk**

For general questions: Open a GitHub issue

---

**Last Updated**: 2026-01-30

## Recent Security Improvements

### Version 1.0.0 (2026-01-30)

**Rate Limiting System**
- Per-user rate limits: 1000 req/hour (users), 5000 req/hour (admins)
- Per-API rate limits to protect external quotas
- HTTP 429 responses with Retry-After headers
- Rate limit headers on all responses (X-RateLimit-*)

**Input Validation**
- Comprehensive validation on all endpoints
- Protection against injection attacks
- Query parameter sanitization
- Date and format validation

**Access Control**
- Admin-only restrictions on sensitive operations
- User deletion requires admin role
- Rate limit monitoring requires appropriate permissions

**Audit Logging**
- User authentication logged
- Rate limit violations tracked
- API quota exceeded events recorded
- Admin actions monitored

See RATE_LIMITING.md and CHANGELOG_RATE_LIMITING.md for detailed information.
