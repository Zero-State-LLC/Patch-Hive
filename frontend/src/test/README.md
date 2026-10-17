# PatchHive Frontend Tests

Component tests for the PatchHive React frontend using Vitest and React Testing Library.

## Test Coverage

**Component Tests** (2 test suites, 50+ assertions):

- ✅ **LoadingSpinner** (24 tests)
  - Rendering with default and custom props
  - SVG structure validation
  - Props validation
  - CSS classes
  - Accessibility

- ✅ **AnimatedLogo** (26 tests)
  - Rendering with animation states
  - SVG structure and definitions
  - Visual elements validation
  - Props validation
  - Accessibility

## Running Tests

### Prerequisites

```bash
cd frontend
npm install
```

### Run All Tests

```bash
# Run tests in watch mode
npm test

# Run tests once
npm run test -- --run

# Run with UI
npm run test:ui

# Generate coverage report
npm run test:coverage
```

### Run Specific Tests

```bash
# Run specific test file
npm test LoadingSpinner.test.tsx

# Run tests matching pattern
npm test -- --grep "Rendering"

# Run in specific component directory
npm test components/
```

## Test Structure

```
frontend/src/
├── test/
│   ├── setup.ts                      # Vitest configuration
│   └── README.md                     # This file
├── components/
│   ├── LoadingSpinner.tsx
│   ├── LoadingSpinner.test.tsx       # Component tests
│   ├── AnimatedLogo.tsx
│   └── AnimatedLogo.test.tsx         # Component tests
```

## Testing Stack

- **Vitest** - Fast test runner built on Vite
- **React Testing Library** - Component testing utilities
- **@testing-library/jest-dom** - Custom matchers
- **@testing-library/user-event** - User interaction simulation
- **jsdom** - DOM implementation for testing
- **@vitest/ui** - Interactive test UI
- **@vitest/coverage-v8** - Code coverage

## Writing Tests

### Test Structure Template

```typescript
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MyComponent } from './MyComponent';

describe('MyComponent', () => {
  describe('Rendering', () => {
    it('renders without crashing', () => {
      render(<MyComponent />);
      expect(screen.getByRole('button')).toBeInTheDocument();
    });
  });

  describe('Interactions', () => {
    it('handles click events', async () => {
      const { user } = renderWithUser(<MyComponent />);
      await user.click(screen.getByRole('button'));
      expect(screen.getByText('Clicked')).toBeInTheDocument();
    });
  });
});
```

### Best Practices

1. **Use Testing Library queries** - Prefer `getByRole`, `getByLabelText`, `getByText` over `querySelector`
2. **Test user behavior** - Focus on what users see and do, not implementation details
3. **Accessibility first** - Tests that use accessible queries ensure better UX
4. **Descriptive test names** - Use clear "should" or action-based descriptions
5. **Organize with describe blocks** - Group related tests logically
6. **Mock external dependencies** - API calls, timers, localStorage, etc.

### Example: Testing User Interactions

```typescript
import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

describe('Interactive Component', () => {
  it('updates on user input', async () => {
    const user = userEvent.setup();
    render(<SearchBar />);

    const input = screen.getByRole('textbox');
    await user.type(input, 'VCO');

    expect(input).toHaveValue('VCO');
  });
});
```

### Example: Testing Async Behavior

```typescript
import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';

describe('Async Component', () => {
  it('loads and displays data', async () => {
    render(<ModuleList />);

    expect(screen.getByText('Loading...')).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText('Plaits')).toBeInTheDocument();
    });
  });
});
```

## Mocking

### Mock API Calls

```typescript
import { vi } from "vitest";
import axios from "axios";

vi.mock("axios");

describe("API Component", () => {
  it("fetches data", async () => {
    axios.get.mockResolvedValue({ data: { modules: [] } });
    // ... test code
  });
});
```

### Mock Router

```typescript
import { BrowserRouter } from 'react-router-dom';

const renderWithRouter = (component) => {
  return render(
    <BrowserRouter>
      {component}
    </BrowserRouter>
  );
};
```

## Coverage Goals

Target coverage metrics:

- **Statements**: >80%
- **Branches**: >75%
- **Functions**: >80%
- **Lines**: >80%

View coverage report:

```bash
npm run test:coverage
open coverage/index.html
```

## CI/CD Integration

Tests run automatically on:

- Push to `main`, `develop`, `claude/**` branches
- Pull requests to `main` or `develop`
- Via GitHub Actions workflow

## Debugging Tests

### Run in Debug Mode

```bash
# Run with verbose output
npm test -- --reporter=verbose

# Run single test file with debugging
npm test -- LoadingSpinner.test.tsx --reporter=verbose
```

### Use Vitest UI

```bash
npm run test:ui
```

Open browser to interact with tests, inspect renders, and see coverage.

### Common Issues

**Issue**: Tests fail with "document is not defined"
**Solution**: Ensure `environment: 'jsdom'` is set in `vitest.config.ts`

**Issue**: SVG tests fail
**Solution**: Check `src/test/setup.ts` has SVG mocks

**Issue**: Animation tests flaky
**Solution**: Use `waitFor` for animated elements

## Resources

- [Vitest Documentation](https://vitest.dev/)
- [React Testing Library](https://testing-library.com/react)
- [Testing Library Queries](https://testing-library.com/docs/queries/about)
- [Jest DOM Matchers](https://github.com/testing-library/jest-dom)

---

**Questions?** Check the [main test README](../../backend/tests/README.md) or open an issue on GitHub.
