![Samba Agents Logo](https://sambanova.ai/hubfs/sambanova-logo-black.png)


# Contributing to SambaNova Agents

First off, thank you for considering contributing to SambaNova Agents! It's people like you that make this tool a great resource for the sales and research community.


## How Can I Contribute?

### Reporting Bugs

Before creating bug reports, please check the issue list as you might find out that you don't need to create one. When you are creating a bug report, please include as many details as possible:

* Use a clear and descriptive title
* Describe the exact steps which reproduce the problem
* Provide specific examples to demonstrate the steps
* Describe the behavior you observed after following the steps
* Explain which behavior you expected to see instead and why
* Include screenshots if possible

### Suggesting Enhancements

Enhancement suggestions are tracked as GitHub issues. When creating an enhancement suggestion, please include:

* A clear and descriptive title
* A detailed description of the proposed functionality
* Any possible implementation details
* Why this enhancement would be useful to most users

### Development Process

1. Fork the repo and create your branch from `main`
2. If you've added code that should be tested, add tests
3. If you've changed APIs, update the documentation
4. Ensure the test suite passes
5. Make sure your code lints
6. Issue that pull request!

### Local Development Setup

1. Clone your fork of the repository
2. Install the required dependencies:

```bash
# Frontend
cd frontend/sales-agent-crew
yarn install

# Backend
cd backend
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -r requirements.txt
```

### Project Structure

```
├── frontend/
│   └── sales-agent-crew/
│       ├── src/
│       │   ├── components/    # Vue components
│       │   ├── routes/       # Vue router configurations
│       │   ├── stores/       # Pinia stores
│       │   └── services/     # API services
└── backend/
    ├── api/
    │   ├── routes/          # FastAPI route handlers
    │   ├── models/          # Data models
    │   └── services/        # Business logic
    └── tests/               # Test files
```

### Adding New Features

#### Adding a New Route

1. Backend Route:
```python
# backend/api/routes/your_route.py
from fastapi import APIRouter

router = APIRouter()

@router.get("/your-endpoint")
async def your_endpoint():
    return {"message": "Your endpoint"}
```

2. Frontend Route:
```javascript
// frontend/sales-agent-crew/src/router/index.js
{
  path: '/your-route',
  name: 'YourRoute',
  component: () => import('@/views/YourView.vue')
}
```

#### Adding a New Agent Type

1. Create a new agent class in `backend/api/agents/`
2. Implement the required interfaces
3. Add the agent to the routing logic
4. Update the frontend to support the new agent type

### Testing

We use the following testing frameworks:

- Backend: pytest
- Frontend: Vitest

```bash
# Run backend tests
cd backend
pytest

# Run frontend tests
cd frontend/sales-agent-crew
yarn test
```

#### Writing Tests

1. Backend Tests:
```python
# backend/tests/test_your_feature.py
def test_your_feature():
    # Your test code here
    assert True
```

2. Frontend Tests:
```javascript
// frontend/sales-agent-crew/tests/YourComponent.test.js
import { mount } from '@vue/test-utils'
import YourComponent from '@/components/YourComponent.vue'

describe('YourComponent', () => {
  test('renders properly', () => {
    const wrapper = mount(YourComponent)
    expect(wrapper.text()).toContain('Expected text')
  })
})
```

### Git Workflow

1. Create a new branch for your feature:
```bash
git checkout -b feature/your-feature-name
```

2. Make your changes and commit using conventional commits:
```bash
git commit -m "feat: add new feature"
git commit -m "fix: resolve bug in existing feature"
```

3. Push to your fork and submit a pull request

### Pull Request Process

1. Update the README.md with details of changes if applicable
2. Update the documentation if you're changing functionality
3. The PR must pass all CI/CD checks
4. Get at least one code review from a maintainer
5. Follow the PR template provided

### Documentation

- Use JSDoc for JavaScript/Vue components
- Use docstrings for Python functions
- Update the README.md for major changes
- Add inline comments for complex logic

### Style Guide

- Python: Follow PEP 8
- JavaScript: Use ESLint configuration
- Vue: Follow Vue Style Guide
- CSS: Follow TailwindCSS best practices

### Releasing

1. Maintainers will handle version bumps
2. Follow semantic versioning
3. Update CHANGELOG.md
4. Tag releases appropriately

## Questions?

Feel free to open an issue or contact the maintainers if you have any questions.

Thank you for contributing to SambaNova Agents! 🎉