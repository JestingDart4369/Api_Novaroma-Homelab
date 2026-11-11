# Contributing to API Gateway

Thank you for your interest in contributing! This document provides guidelines for contributing to the project.

## 📋 Table of Contents

- [Code of Conduct](#code-of-conduct)
- [How Can I Contribute?](#how-can-i-contribute)
- [Development Setup](#development-setup)
- [Coding Standards](#coding-standards)
- [Commit Guidelines](#commit-guidelines)
- [Pull Request Process](#pull-request-process)

---

## 📜 Code of Conduct

### Our Standards

- **Be Respectful**: Treat everyone with respect and kindness
- **Be Constructive**: Provide helpful feedback and suggestions
- **Be Patient**: Remember that contributors have varying levels of experience
- **Be Open-Minded**: Welcome diverse perspectives and ideas

### Unacceptable Behavior

- Harassment, discrimination, or offensive comments
- Personal attacks or insults
- Spam or advertising unrelated to the project
- Publishing private information without permission

---

## 🤝 How Can I Contribute?

### Reporting Bugs

Found a bug? Help us fix it!

1. **Check existing issues** - Someone might have already reported it
2. **Create a new issue** - Use the bug report template
3. **Include details**:
   - Steps to reproduce
   - Expected vs actual behavior
   - Environment (OS, Python version, Docker version)
   - Relevant logs or error messages

### Suggesting Features

Have an idea for a new feature?

1. **Check existing issues** - It might already be planned
2. **Open a feature request** - Use the feature request template
3. **Describe clearly**:
   - Problem it solves
   - Proposed solution
   - Alternative approaches considered

### Improving Documentation

Documentation improvements are always welcome!

- Fix typos or unclear explanations
- Add examples or tutorials
- Improve API documentation
- Update wiki pages

---

## 🛠️ Development Setup

### Prerequisites

- Python 3.12+
- Docker & Docker Compose
- Git

### Local Setup

1. **Fork and clone**
   ```bash
   git clone https://github.com/YOUR_USERNAME/ApiServer_Novaroma.git
   cd ApiServer_Novaroma
   ```

2. **Create environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your test credentials
   ```

4. **Run locally (without Docker)**
   ```bash
   uvicorn oldapp.main:oldapp --reload --port 8080
   ```

5. **Run with Docker**
   ```bash
   docker compose up -d --build
   ```

### Testing

```bash
# Test health endpoint
curl http://localhost:8080/health

# Test authentication
curl -X POST http://localhost:8080/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"your-password"}'

# Test protected endpoint
curl "http://localhost:8080/weather?city=London" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

## 📐 Coding Standards

### Python Style Guide

- Follow **PEP 8** style guidelines
- Use **type hints** for function parameters and return values
- Write **docstrings** for functions and classes
- Keep functions **focused** and **single-purpose**

### Code Example

```python
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException

router = APIRouter(prefix="/example", tags=["example"])

@router.get("/endpoint")
async def example_endpoint(
    param: str,
    optional_param: Optional[str] = None,
    user: dict = Depends(get_current_user)
) -> dict:
    """
    Brief description of what this endpoint does.

    Args:
        param: Description of required parameter
        optional_param: Description of optional parameter
        user: Authenticated user from dependency

    Returns:
        dict: Description of return value
    """
    # Implementation here
    return {"result": "success"}
```

### File Organization

```
app/
├── main.py          # Application entry point
├── models.py        # Database models
├── auth.py          # Authentication logic
├── security.py      # Security dependencies
├── rate_limit.py    # Rate limiting system
├── notifications.py # Email notification system
└── routes/          # API route modules
    ├── users.py
    ├── weather.py
    ├── forecast.py
    ├── geocode.py
    ├── ipregistry.py
    ├── telephone.py
    ├── nasa.py
    ├── openlibrary.py
    ├── email.py
    └── rate_limits.py
```

---

## 📝 Commit Guidelines

### Commit Message Format

```
<type>: <subject>

<body>

<footer>
```

### Types

- **feat**: New feature
- **fix**: Bug fix
- **docs**: Documentation changes
- **style**: Code style changes (formatting, no logic change)
- **refactor**: Code refactoring
- **test**: Adding or updating tests
- **chore**: Maintenance tasks

### Examples

```
feat: Add hourly weather forecast endpoint

- Implement /forecast/hourly route
- Add OpenWeather API integration
- Update documentation

Closes #123
```

```
fix: Correct password hashing for long passwords

- Pre-hash passwords >72 bytes with SHA-256
- Prevents bcrypt limitation error
- Add tests for long password handling

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
```

---

## 🔄 Pull Request Process

### Before Submitting

1. ✅ **Test your changes** - Ensure everything works
2. ✅ **Update documentation** - Keep docs in sync with code
3. ✅ **Follow code style** - Match existing patterns
4. ✅ **Write clear commits** - Follow commit guidelines

### Submission Steps

1. **Create a branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**
   ```bash
   git add .
   git commit -m "feat: Add your feature"
   ```

3. **Push to your fork**
   ```bash
   git push origin feature/your-feature-name
   ```

4. **Open a Pull Request**
   - Use a clear title
   - Fill out the PR template
   - Link related issues
   - Describe what changed and why

### PR Review Process

1. **Automated checks** - Must pass (if configured)
2. **Code review** - Maintainer will review
3. **Requested changes** - Address feedback
4. **Approval** - Once approved, PR will be merged
5. **Merge** - Squash and merge to main branch

### After Merge

- Your contribution will be in the next release
- You'll be added to contributors list
- Thank you for contributing! 🎉

---

## 🐛 Debugging Tips

### Common Issues

**Issue**: `SQLAlchemy database locked`
- **Solution**: Stop all running instances, delete `data/gateway.db-journal`

**Issue**: `Port 8080 already in use`
- **Solution**: Stop conflicting service or change port in `docker-compose.yml`

**Issue**: `JWT token invalid`
- **Solution**: Ensure `JWT_SECRET` is consistent between restarts

### Docker Debugging

```bash
# View logs
docker compose logs -f api-gateway

# Access container shell
docker compose exec api-gateway /bin/bash

# Restart services
docker compose restart

# Rebuild from scratch
docker compose down
docker compose up -d --build
```

---

## 💡 Feature Development Guidelines

### Adding a New API Endpoint

1. **Create route file**: `app/routes/newapi.py`
2. **Implement logic**: Handle external API calls with `httpx.AsyncClient`
3. **Add authentication**: Use `Depends(get_current_user)`
4. **Add rate limiting**:
   - User rate limit: `Depends(check_user_rate_limit)`
   - API rate limit: Create API-specific limiter in `app/rate_limit.py`
5. **Input validation**: Validate all parameters before external API calls
6. **Register router**: Add to `app/main.py`
7. **Update documentation**: Add to `CLAUDE.md`, `README.md`, and `index.html`
8. **Test thoroughly**: Verify functionality and rate limiting

**Example with Rate Limiting:**

```python
from fastapi import APIRouter, Depends, HTTPException
from app.security import get_current_user
from app.models import User
from app.rate_limit import check_user_rate_limit, get_api_limiter
import httpx

router = APIRouter(tags=["newapi"])

# Create API-specific rate limiter
check_newapi_limit = get_api_limiter("newapi")

@router.get("/newapi/endpoint")
async def new_endpoint(
    param: str,
    user: User = Depends(get_current_user),
    _rate_limit: dict = Depends(check_user_rate_limit),
    _api_limit: None = Depends(check_newapi_limit)
):
    """
    Description of endpoint.

    Rate Limits:
    - User: 1000 req/hour (regular), 5000 req/hour (admin)
    - NewAPI: 2000 req/hour (shared across all users)
    """
    # Validate input
    if not param or len(param) > 100:
        raise HTTPException(status_code=400, detail="Invalid param")

    # Call external API
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get("https://api.example.com", params={"q": param})

    if response.status_code != 200:
        raise HTTPException(status_code=502, detail="External API failed")

    return response.json()
```

Then add to `app/rate_limit.py`:

```python
API_RATE_LIMITS = {
    # ... existing ...
    "newapi": 2000,  # 2000 requests per hour
}
```

### Adding Environment Variables

1. **Add to `.env`**: Include actual value
2. **Add to `.env.example`**: Use placeholder with descriptive comment
3. **Document in README**: Add to configuration table
4. **Document in CLAUDE.md**: Add to environment variables section
5. **Access in code**: Use `os.environ["VARIABLE_NAME"]` or `os.environ.get("VARIABLE_NAME", "default")`

### Rate Limiting Best Practices

When adding new endpoints:
- Always include both user and API rate limiting
- Document rate limits in endpoint docstrings
- Use descriptive API names matching the service
- Set conservative API limits based on free tier quotas
- Test rate limiting with multiple rapid requests
- Ensure proper error messages on HTTP 429

### Input Validation Guidelines

All endpoints should validate inputs:
- Check required parameters exist
- Validate string lengths (prevent DOS attacks)
- Validate date formats before use
- Sanitize user input before external API calls
- Validate numeric ranges
- Check enum values against allowed lists
- Return clear error messages (HTTP 400) for invalid input

---

## 📬 Questions?

- **Issues**: Open an issue for bugs or questions
- **Discussions**: Use GitHub Discussions for general questions
- **Security**: Email security issues privately (see SECURITY.md)

---

## 📚 Documentation Requirements

When contributing, ensure documentation is updated:

1. **Code Documentation**
   - Add docstrings to all functions
   - Include rate limit information in endpoint docstrings
   - Document parameters and return values
   - Add inline comments for complex logic

2. **User Documentation**
   - Update README.md with new features
   - Add examples to CLAUDE.md
   - Update API endpoint lists
   - Add configuration variables

3. **Security Documentation**
   - Document any security implications
   - Update SECURITY.md if adding authentication/authorization
   - Document rate limits and quotas

## 🧪 Testing Requirements

Before submitting a PR:

1. **Manual Testing**
   - Test with valid inputs
   - Test with invalid inputs (expect 400 errors)
   - Test rate limiting (make rapid requests)
   - Test authentication (valid and invalid tokens)
   - Test admin-only endpoints with user role

2. **Rate Limit Testing**
   ```bash
   # Test user rate limit
   for i in {1..10}; do
     curl -H "Authorization: Bearer $TOKEN" \
       http://localhost:8080/your-endpoint
   done
   ```

3. **Security Testing**
   - Try accessing admin endpoints as regular user
   - Try accessing endpoints without JWT token
   - Try SQL injection in parameters
   - Try excessively long input strings

Thank you for contributing to API Gateway! 🙌
