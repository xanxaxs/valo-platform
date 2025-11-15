# CLAUDE.md - AI Assistant Guide for valo-platform

> **Last Updated:** 2025-11-15
> **Status:** Initial Setup - Repository is new/empty

This document serves as a comprehensive guide for AI assistants (like Claude) working on the valo-platform codebase. It contains essential information about the project structure, development workflows, coding conventions, and best practices.

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Repository Structure](#repository-structure)
3. [Development Environment](#development-environment)
4. [Development Workflows](#development-workflows)
5. [Code Conventions](#code-conventions)
6. [Testing Guidelines](#testing-guidelines)
7. [Git Workflow](#git-workflow)
8. [Common Tasks](#common-tasks)
9. [Architecture Patterns](#architecture-patterns)
10. [Important Context for AI Assistants](#important-context-for-ai-assistants)

---

## Project Overview

### About valo-platform

**Status:** Project initialization phase

valo-platform is [DESCRIPTION TO BE ADDED - describe the purpose, goals, and main features of this platform].

### Key Technologies

_To be populated as the tech stack is established. Common sections include:_

- **Frontend:** (e.g., React, Vue, Angular, etc.)
- **Backend:** (e.g., Node.js, Python, Go, etc.)
- **Database:** (e.g., PostgreSQL, MongoDB, etc.)
- **Infrastructure:** (e.g., Docker, Kubernetes, AWS, etc.)
- **Build Tools:** (e.g., Webpack, Vite, etc.)

### Project Goals

_Document the main objectives and success criteria of this platform._

---

## Repository Structure

### Current Structure

```
valo-platform/
├── .git/           # Git repository metadata
└── CLAUDE.md       # This file
```

### Planned Structure

_Update this section as the project structure develops. Example:_

```
valo-platform/
├── src/                    # Source code
│   ├── components/         # Reusable components
│   ├── services/           # Business logic services
│   ├── utils/              # Utility functions
│   ├── types/              # TypeScript type definitions
│   └── config/             # Configuration files
├── tests/                  # Test files
├── docs/                   # Documentation
├── scripts/                # Build and utility scripts
├── public/                 # Static assets
├── .github/                # GitHub workflows and templates
├── package.json            # Dependencies and scripts
├── tsconfig.json           # TypeScript configuration
├── .eslintrc.js            # ESLint configuration
├── .prettierrc             # Prettier configuration
└── README.md               # Project README
```

### Key Directories

_Describe the purpose of each major directory:_

- **src/**: Main application source code
- **tests/**: All test files (unit, integration, e2e)
- **docs/**: Project documentation
- **scripts/**: Automation and build scripts

---

## Development Environment

### Prerequisites

_List required software and versions:_

- Node.js: (version TBD)
- npm/yarn/pnpm: (version TBD)
- Database: (if applicable)
- Other tools: (Docker, etc.)

### Setup Instructions

```bash
# Clone the repository
git clone <repository-url>
cd valo-platform

# Install dependencies
npm install  # or yarn/pnpm

# Set up environment variables
cp .env.example .env
# Edit .env with your local configuration

# Run the development server
npm run dev
```

### Environment Variables

_Document required environment variables:_

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| TBD | TBD | Yes/No | TBD |

---

## Development Workflows

### Running the Application

```bash
# Development mode
npm run dev

# Production build
npm run build

# Start production server
npm start
```

### Available Scripts

_Document all npm/yarn scripts in package.json:_

| Script | Command | Description |
|--------|---------|-------------|
| `dev` | `npm run dev` | Start development server |
| `build` | `npm run build` | Create production build |
| `test` | `npm test` | Run test suite |
| `lint` | `npm run lint` | Run linter |
| `format` | `npm run format` | Format code with Prettier |

### Code Quality Tools

- **Linter:** ESLint (configuration TBD)
- **Formatter:** Prettier (configuration TBD)
- **Type Checker:** TypeScript (if applicable)
- **Pre-commit Hooks:** Husky + lint-staged (if applicable)

---

## Code Conventions

### General Principles

1. **Clarity over Cleverness:** Write code that is easy to understand
2. **Consistency:** Follow established patterns in the codebase
3. **Documentation:** Comment complex logic, not obvious code
4. **DRY (Don't Repeat Yourself):** Extract common patterns into reusable functions
5. **SOLID Principles:** Follow object-oriented design principles

### Naming Conventions

_Update based on chosen language/framework:_

- **Files:** `kebab-case.ts` or `PascalCase.tsx` for components
- **Variables/Functions:** `camelCase`
- **Classes/Components:** `PascalCase`
- **Constants:** `UPPER_SNAKE_CASE`
- **Interfaces/Types:** `PascalCase` with descriptive names

### File Organization

- One component/class per file (exceptions for tightly coupled small utilities)
- Group related files in feature directories
- Keep files under 300 lines when possible
- Use index files for cleaner imports

### Code Style

_Document specific style preferences:_

- **Indentation:** 2 or 4 spaces (specify)
- **Quotes:** Single or double quotes (specify)
- **Semicolons:** Required or optional (specify)
- **Line Length:** 80, 100, or 120 characters (specify)
- **Trailing Commas:** Yes or no (specify)

### Component/Function Structure

_Example for React components or similar:_

```typescript
// 1. Imports
import { useState } from 'react';
import { SomeType } from './types';

// 2. Types/Interfaces
interface ComponentProps {
  // ...
}

// 3. Component definition
export const Component = ({ prop1, prop2 }: ComponentProps) => {
  // 4. Hooks
  const [state, setState] = useState();

  // 5. Handlers
  const handleClick = () => {
    // ...
  };

  // 6. Effects
  useEffect(() => {
    // ...
  }, []);

  // 7. Render
  return (
    // JSX
  );
};
```

---

## Testing Guidelines

### Testing Strategy

_Define testing approach:_

- **Unit Tests:** Test individual functions and components in isolation
- **Integration Tests:** Test interactions between modules
- **E2E Tests:** Test complete user workflows
- **Target Coverage:** Aim for X% code coverage (specify)

### Test File Locations

- Co-located with source files: `component.test.ts` alongside `component.ts`
- OR in separate `tests/` or `__tests__/` directories

### Writing Tests

```typescript
// Example test structure
describe('ComponentName', () => {
  it('should do something specific', () => {
    // Arrange
    const input = 'test';

    // Act
    const result = someFunction(input);

    // Assert
    expect(result).toBe('expected');
  });
});
```

### Running Tests

```bash
# Run all tests
npm test

# Run tests in watch mode
npm run test:watch

# Run tests with coverage
npm run test:coverage

# Run specific test file
npm test -- path/to/test.spec.ts
```

---

## Git Workflow

### Branch Naming

Follow this convention:

- `main` or `master` - Production-ready code
- `develop` - Integration branch for features
- `feature/description` - New features
- `fix/description` - Bug fixes
- `hotfix/description` - Urgent production fixes
- `refactor/description` - Code refactoring
- `docs/description` - Documentation updates
- `claude/*` - AI assistant work branches

### Commit Message Format

Follow conventional commits:

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:**
- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation changes
- `style:` Code style changes (formatting, etc.)
- `refactor:` Code refactoring
- `test:` Adding or updating tests
- `chore:` Maintenance tasks

**Examples:**
```
feat(auth): add user authentication system

Implement JWT-based authentication with login and registration endpoints.

Closes #123
```

```
fix(api): resolve null pointer exception in user service

Added null check before accessing user properties.
```

### Pull Request Process

1. Create a feature branch from `develop` (or `main`)
2. Make your changes with clear, atomic commits
3. Write/update tests for your changes
4. Update documentation if needed
5. Ensure all tests pass and code is formatted
6. Create a pull request with a clear description
7. Address review feedback
8. Squash or rebase commits if requested
9. Merge after approval

### Code Review Guidelines

**For Reviewers:**
- Check for correctness and potential bugs
- Verify tests are adequate
- Ensure code follows conventions
- Look for security issues
- Suggest improvements, don't demand perfection

**For Authors:**
- Respond to all comments
- Explain your reasoning when disagreeing
- Make requested changes or discuss alternatives
- Keep PRs focused and reasonably sized

---

## Common Tasks

### Adding a New Feature

1. Create a feature branch: `git checkout -b feature/my-feature`
2. Implement the feature following code conventions
3. Write tests for the new functionality
4. Update documentation (README, CLAUDE.md, etc.)
5. Create a pull request

### Fixing a Bug

1. Create a fix branch: `git checkout -b fix/bug-description`
2. Write a failing test that reproduces the bug
3. Fix the bug
4. Verify the test now passes
5. Create a pull request

### Refactoring Code

1. Ensure tests exist for the code being refactored
2. Make incremental changes
3. Run tests after each change
4. Document why the refactoring improves the code
5. Create a pull request with clear before/after examples

### Adding Dependencies

1. Evaluate if the dependency is necessary
2. Check license compatibility
3. Verify package is well-maintained and secure
4. Add with exact version: `npm install --save-exact package-name`
5. Document the dependency's purpose
6. Update CLAUDE.md if it affects development workflow

---

## Architecture Patterns

### Design Patterns Used

_Document key architectural patterns:_

- **MVC/MVP/MVVM:** (if applicable)
- **Service Layer:** Business logic separation
- **Repository Pattern:** Data access abstraction
- **Factory Pattern:** Object creation
- **Observer Pattern:** Event handling
- **Others:** Document as they emerge

### Module Dependencies

_Diagram or describe how major modules interact:_

```
┌─────────────┐
│   Frontend  │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  API Layer  │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   Services  │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Database   │
└─────────────┘
```

### State Management

_Describe state management approach:_

- Global state: (Redux, Zustand, Context API, etc.)
- Local state: (Component state)
- Server state: (React Query, SWR, etc.)

### Error Handling

_Document error handling patterns:_

- Try-catch blocks for async operations
- Error boundaries for React components
- Centralized error logging
- User-friendly error messages

### Security Considerations

- Input validation and sanitization
- Authentication and authorization
- CORS configuration
- Environment variable protection
- SQL injection prevention
- XSS protection
- CSRF tokens (if applicable)

---

## Important Context for AI Assistants

### Development Philosophy

When working on this codebase as an AI assistant:

1. **Understand Before Changing:** Read related code before making modifications
2. **Follow Existing Patterns:** Match the style and patterns already in use
3. **Write Tests:** Include tests with new features and bug fixes
4. **Document Changes:** Update comments and documentation
5. **Security First:** Always consider security implications
6. **Ask When Uncertain:** Clarify requirements before implementing

### Common Pitfalls to Avoid

- Don't introduce new dependencies without justification
- Avoid mixing different naming conventions
- Don't skip error handling
- Avoid deeply nested code (keep complexity low)
- Don't commit commented-out code
- Avoid large, monolithic functions (keep them focused)
- Don't ignore TypeScript errors or linter warnings
- Avoid premature optimization

### AI-Specific Guidelines

**When Reading Code:**
1. Start with README.md and CLAUDE.md
2. Check package.json for available scripts
3. Look for existing tests to understand expected behavior
4. Review recent commits to understand context

**When Writing Code:**
1. Match existing code style exactly
2. Add inline comments for complex logic
3. Write descriptive variable and function names
4. Keep functions small and focused
5. Add JSDoc comments for public APIs

**When Fixing Bugs:**
1. Reproduce the bug first
2. Write a failing test
3. Fix the minimal amount of code
4. Verify the test passes
5. Check for similar bugs elsewhere

**When Refactoring:**
1. Ensure good test coverage first
2. Make small, incremental changes
3. Run tests after each change
4. Document the reasoning in commit messages

### Key Files to Check Before Major Changes

- `package.json` - Dependencies and scripts
- `tsconfig.json` or similar - Type/compile configuration
- `.eslintrc.*` - Linting rules
- `.prettierrc` - Formatting rules
- `README.md` - Project overview
- This file (CLAUDE.md) - AI assistant guide

### Questions to Ask Before Implementation

1. Does this feature align with project goals?
2. Is there an existing pattern for this?
3. What's the security impact?
4. What's the performance impact?
5. How will this be tested?
6. What documentation needs updating?
7. Are there edge cases to consider?
8. Could this break existing functionality?

### Preferred Approaches

_Document team preferences:_

- **Error Handling:** (e.g., prefer async/await over promises)
- **Styling:** (e.g., CSS Modules, styled-components, Tailwind)
- **Data Fetching:** (e.g., fetch API, axios, GraphQL client)
- **Form Handling:** (e.g., React Hook Form, Formik, native)
- **Routing:** (e.g., React Router, Next.js routing)

---

## Maintenance

### Updating This Document

This document should be updated when:

- Project structure changes significantly
- New development tools are adopted
- Coding conventions are established or changed
- New architectural patterns are introduced
- Common issues or questions arise
- Dependencies or tech stack changes

### Document Review

- Review quarterly or after major changes
- Ensure accuracy of all sections
- Remove outdated information
- Add new patterns and conventions as they emerge

### Contact/Ownership

_If applicable, list maintainers or how to get help:_

- **Primary Maintainer:** TBD
- **Questions:** Open an issue or discussion
- **Suggestions:** Submit a PR to update this file

---

## Additional Resources

### Documentation

- [Project README](./README.md) - Overview and quick start
- [API Documentation](./docs/api.md) - API reference (TBD)
- [Architecture Decision Records](./docs/adr/) - Design decisions (TBD)

### External Resources

- Language/Framework official documentation
- Style guides and best practices
- Related projects or examples

---

## Version History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.0.0 | 2025-11-15 | Initial CLAUDE.md template created | Claude AI |

---

**Note to Future Contributors:** Please keep this document updated as the project evolves. An accurate CLAUDE.md makes it much easier for AI assistants to provide effective help.
