# Contributing to BeakerHub

Thank you for your interest in contributing to BeakerHub! This document provides guidelines and instructions for contributing.

## Table of Contents

- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [How to Contribute](#how-to-contribute)
- [Coding Standards](#coding-standards)
- [Testing](#testing)
- [Documentation](#documentation)
- [Pull Request Process](#pull-request-process)

## Getting Started

1. **Read the documentation**:
   - [Quick Start Guide](docs/QUICKSTART.md) - Get the project running
   - [Development Guide](docs/DEVELOPMENT.md) - Understand the codebase
   - [Architecture Docs](docs/vue-jupyterhub-integration.md) - Learn the architecture

2. **Set up your environment**:
   ```bash
   git clone https://github.com/jataware/beakerhub.git
   cd beakerhub
   make dev-setup
   ```

3. **Explore the codebase**:
   ```bash
   # View project structure
   tree -L 2 -I 'node_modules|__pycache__|.git'

   # Check what's running
   make -C helm pods
   ```

## Development Setup

See the [Development Guide](docs/DEVELOPMENT.md#development-environment) for detailed setup instructions.

### Prerequisites

- Docker 20.10+
- kind 0.20.0+
- kubectl 1.27+
- Helm 3.12+
- Python 3.10+
- Node.js 20+
- make

### Quick Setup

```bash
# Complete setup
make dev-setup

# Verify installation
make -C helm status
```

## How to Contribute

### Reporting Bugs

1. **Check existing issues** to avoid duplicates
2. **Use the issue template** if available
3. **Include**:
   - Clear description of the bug
   - Steps to reproduce
   - Expected vs actual behavior
   - Logs (use `make -C helm logs-hub` or `make -C helm logs-proxy`)
   - Environment details (OS, versions)

### Suggesting Features

1. **Check existing issues** for similar requests
2. **Describe the use case** clearly
3. **Explain the expected behavior**
4. **Consider implementation** if possible

### Contributing Code

1. **Find an issue** to work on or create one
2. **Fork the repository**
3. **Create a feature branch**:
   ```bash
   git checkout -b feature/your-feature-name
   ```
4. **Make your changes** following our [coding standards](#coding-standards)
5. **Test your changes**:
   ```bash
   make sync                    # Deploy changes
   make -C helm logs-hub        # Check logs
   ```
6. **Commit your changes** using [conventional commits](#commit-messages)
7. **Push and create a pull request**

## Coding Standards

### Python

- Follow **PEP 8** style guide
- Use **type hints** where appropriate
- Write **docstrings** for public functions/classes
- Use **black** for formatting:
  ```bash
  black src/beakerhub
  ```
- Use **mypy** for type checking:
  ```bash
  mypy src/beakerhub
  ```

Example:
```python
from typing import Optional

def get_user_pod(username: str) -> Optional[dict]:
    """
    Retrieve the Kubernetes pod for a given user.

    Args:
        username: The JupyterHub username

    Returns:
        Pod dictionary if found, None otherwise
    """
    # Implementation
    pass
```

### TypeScript/JavaScript

- Follow the project's **ESLint configuration**
- Use **TypeScript** for type safety
- Write **JSDoc comments** for complex functions
- Run linter before committing:
  ```bash
  cd ui && npm run lint
  ```

Example:
```typescript
/**
 * Fetch user notebooks from the API
 * @param username - The user's username
 * @returns Promise resolving to array of notebooks
 */
async function fetchNotebooks(username: string): Promise<Notebook[]> {
  // Implementation
}
```

### Commit Messages

Use **Conventional Commits** format:

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

**Types**:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

**Examples**:
```bash
feat(ui): add notebook list view
fix(hub): resolve user pod spawning issue
docs: update development setup guide
refactor(proxy): simplify routing logic
```

### File Organization

- **Python**: Place new modules in `src/beakerhub/`
- **UI Components**: Place in `ui/src/components/`
- **UI Pages**: Place in `ui/src/pages/`
- **Tests**: Mirror source structure in `tests/`
- **Docs**: Place in `docs/`

## Testing

### Running Tests

```bash
# Python tests
pytest
pytest --cov=src/beakerhub  # With coverage

# UI unit tests
cd ui && npm run test:unit

# UI e2e tests
cd ui && npm run test:e2e

# Manual integration testing
make sync
# Test manually in browser
```

### Writing Tests

#### Python Tests

```python
# tests/test_handlers.py
import pytest
from beakerhub.handlers import VueSPAHandler

def test_vue_spa_handler():
    """Test that VueSPAHandler serves the Vue app"""
    # Test implementation
    pass
```

#### UI Tests

```typescript
// ui/src/components/__tests__/NotebookList.test.ts
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import NotebookList from '../NotebookList.vue'

describe('NotebookList', () => {
  it('renders notebook items', () => {
    // Test implementation
  })
})
```

### Test Requirements

- **New features** must include tests
- **Bug fixes** should include regression tests
- **Aim for high coverage** of critical paths
- **Test both success and error cases**

## Documentation

### When to Update Docs

Update documentation when you:
- Add new features
- Change configuration options
- Modify public APIs
- Fix bugs that affect usage
- Change development workflow

### Documentation Types

1. **Code Comments**: For complex logic
2. **Docstrings/JSDoc**: For public functions/classes
3. **README Updates**: For user-facing changes
4. **Development Guide**: For developer workflow changes
5. **Architecture Docs**: For design changes

### Writing Good Documentation

- **Be clear and concise**
- **Include examples** where helpful
- **Keep it up to date**
- **Use proper markdown formatting**
- **Add code blocks** with syntax highlighting

Example:
````markdown
## Using the API

Fetch notebooks for a user:

```python
notebooks = await hub.api.get_notebooks(username)
```

This returns a list of notebook objects with the following structure:

```python
{
    'name': 'my-notebook',
    'path': '/home/user/my-notebook.ipynb',
    'last_modified': '2024-01-01T00:00:00Z'
}
```
````

## Pull Request Process

### Before Submitting

1. **Test your changes**:
   ```bash
   make sync
   make -C helm logs-hub
   # Verify functionality
   ```

2. **Run linters and tests**:
   ```bash
   # Python
   black src/beakerhub
   mypy src/beakerhub
   pytest

   # UI
   cd ui
   npm run lint
   npm run type-check
   npm run test:unit
   ```

3. **Update documentation** if needed

4. **Ensure commits follow conventions**

### Submitting a Pull Request

1. **Push your branch** to your fork

2. **Create pull request** with:
   - **Clear title** describing the change
   - **Description** explaining:
     - What changes were made
     - Why they were made
     - How to test them
   - **Link to related issue** if applicable

3. **Respond to feedback** promptly

4. **Keep PR focused** - one feature/fix per PR

### PR Review Process

1. **Automated checks** must pass:
   - Linting
   - Tests
   - Build

2. **Code review** by maintainers:
   - Code quality
   - Testing coverage
   - Documentation
   - Design decisions

3. **Address feedback**:
   - Make requested changes
   - Push updates to the same branch
   - Respond to comments

4. **Approval and merge**:
   - Maintainer approves
   - PR is merged
   - Branch can be deleted

### PR Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## How to Test
1. Step 1
2. Step 2
3. Expected result

## Checklist
- [ ] Tests added/updated
- [ ] Documentation updated
- [ ] Linting passes
- [ ] Tested locally

## Related Issues
Fixes #123
```

## Code Review Guidelines

### For Authors

- **Keep PRs small** and focused
- **Provide context** in description
- **Test thoroughly** before requesting review
- **Be responsive** to feedback
- **Be open** to suggestions

### For Reviewers

- **Be respectful** and constructive
- **Explain reasoning** for requested changes
- **Acknowledge good work**
- **Suggest improvements** with examples
- **Focus on**:
  - Correctness
  - Maintainability
  - Performance
  - Security
  - Testing

## Getting Help

- **Documentation**: Check [docs/](docs/) directory
- **Issues**: Search existing issues
- **Logs**: Use `make -C helm logs-hub` or `make -C helm logs-proxy`
- **Troubleshooting**: See [Quick Start troubleshooting](docs/QUICKSTART.md#troubleshooting)

## Community Guidelines

- **Be respectful** and inclusive
- **Welcome newcomers**
- **Share knowledge**
- **Give constructive feedback**
- **Follow the code of conduct** (if available)

## License

By contributing, you agree that your contributions will be licensed under the same license as the project (MIT).

---

Thank you for contributing to BeakerHub! Your efforts help make this project better for everyone.
