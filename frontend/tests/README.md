# Frontend testing architecture

The frontend uses Vitest, Testing Library, jsdom, and `*.test.ts` / `*.test.tsx`
filenames. Tests follow a deliberate hybrid structure: feature behavior stays with
its owning feature, while cross-feature suites and reusable infrastructure live in
the top-level `tests` directory.

```text
frontend/
├── src/features/<feature>/__tests__/
│   ├── unit/          Pure functions, hooks, reducers, and feature utilities
│   ├── components/    One component exercised through its public UI
│   ├── integration/   Multiple feature modules working together
│   ├── pages/         Page and route-level behavior
│   ├── fixtures/      Static feature-owned scenarios, when needed
│   ├── factories/     Feature-owned data builders
│   └── mocks/         Feature-owned boundaries and stubs, when needed
└── tests/
    ├── accessibility/ Cross-feature axe and keyboard accessibility suites
    ├── e2e/           Browser E2E tests when an E2E runner is introduced
    ├── fixtures/      Truly reusable static scenarios, when needed
    ├── helpers/       Reusable assertions and async helpers
    ├── mocks/         Shared browser or API boundary stubs, when needed
    ├── render/        Provider-aware Testing Library render functions
    └── setup/         Vitest global setup only
```

Directories that have no implementation are intentionally not kept as empty
placeholders. Add one only when its first owned file is introduced.

## Ownership rules

- Put a component test in its feature's `__tests__/components` directory. A test
  that composes several modules belongs in `integration` instead.
- Put pure hooks and utility tests in the feature's `__tests__/unit` directory.
- Put page components and route-state behavior in `__tests__/pages`.
- Put axe scans and other dedicated accessibility suites in
  `tests/accessibility`, grouped by feature. Keep keyboard behavior in the owning
  component or integration suite when it is part of that feature requirement.
- Keep a fixture, mock, or factory feature-local unless at least two independent
  features need it. Only then promote it to the corresponding top-level `tests`
  directory.
- Move a render or helper utility to top-level `tests` only when it removes
  repeated setup across multiple suites. One-off setup stays in its test file.
- Put browser E2E tests in `tests/e2e`. They are excluded from Vitest and must use
  the repository's selected E2E runner; no E2E runner is currently configured.
- Production modules under `src` may not import the `@test/*` alias. ESLint
  enforces this boundary.

## Commands

```bash
pnpm test
pnpm test:unit
pnpm test:components
pnpm test:integration
pnpm test:pages
pnpm test:accessibility
pnpm test:coverage
pnpm typecheck
pnpm lint
```

`tests/setup/vitest.setup.ts` is the only global setup entry. Prefer local mocks
and explicit builders so suites remain deterministic and independently runnable.
