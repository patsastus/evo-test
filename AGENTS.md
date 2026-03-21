# AGENTS.md - Shadow Evolution Developer Guide

## Overview

Shadow Evolution is a React/TypeScript application that generates 3D tree structures to match target shadow images using a genetic algorithm. It uses Vite as the build tool, Tailwind CSS for styling, and React Three Fiber for 3D rendering.

---

## Build, Lint, and Test Commands

### Development
```bash
npm run dev          # Start development server on port 3000
```

### Building
```bash
npm run build        # Run TypeScript check, then build for production
npm run preview      # Preview the built production app
```

### Linting
```bash
npm run lint         # Run ESLint on all .ts and .tsx files
```

### Testing
**No test framework is currently configured.** If adding tests, use Vitest or React Testing Library.

To run a single test file when tests are added:
```bash
npx vitest run src/components/__tests__/ComponentName.test.tsx
```

---

## Code Style Guidelines

### General Rules
- Use **2 spaces** for indentation
- Use **single quotes** for strings in TypeScript/JSX
- Add **trailing commas** in multiline objects/arrays
- Use **semicolons** at the end of statements
- Maximum line length: **100 characters** (soft limit)

### Imports
- Group imports in this order:
  1. External libraries (React, three, @react-three/*, recharts, lucide-react)
  2. Internal components (./components/*)
  3. Internal services/utilities (./services/*)
  4. Types (./types)
- Use path alias `@/*` for internal imports (e.g., `@/types`, `@/components/Scene3D`)

```typescript
// Example import order
import React, { useState, useMemo } from 'react';
import { Canvas } from '@react-three/fiber';
import { OrbitControls } from '@react-three/drei';
import * as THREE from 'three';
import { SceneData, TreeNode } from '@/types';
import { generateScenes } from '@/services/mockBackend';
import { Gallery } from '@/components/Gallery';
```

### TypeScript Conventions
- **Always use explicit types** for function parameters and return types
- Use `interface` for object shapes, `type` for unions/intersections
- Use `React.FC<Props>` for functional components
- Use `enum` for fixed sets of values

```typescript
interface TreeNode {
  id: string;
  x: number;
  y: number;
  z: number;
  radius: number;
  parentId: string | null;
}

export const MyComponent: React.FC<MyComponentProps> = ({ prop1, prop2 }) => {
  // ...
};
```

### Naming Conventions
- **Components**: PascalCase (e.g., `Scene3D.tsx`, `ControlPanel.tsx`)
- **Interfaces/Types**: PascalCase (e.g., `TreeNode`, `SceneData`)
- **Functions/Variables**: camelCase
- **Constants**: UPPER_SNAKE_CASE for true constants, camelCase otherwise
- **Files**: PascalCase for components, camelCase for utilities

### Component Structure
```typescript
import React from 'react';
import { ComponentA } from './components/ComponentA';
import { SomeType } from '@/types';

interface MyComponentProps {
  requiredProp: string;
  optionalProp?: number;
}

export const MyComponent: React.FC<MyComponentProps> = ({
  requiredProp,
  optionalProp = 10
}) => {
  // Hooks first
  const [state, setState] = useState<string>('');
  
  // Memoized values
  const derivedValue = useMemo(() => {
    return state.length * 2;
  }, [state]);

  // Event handlers
  const handleClick = (e: React.MouseEvent) => {
    // ...
  };

  // Render
  return (
    <div className="...">
      {/* ... */}
    </div>
  );
};
```

### Error Handling
- Use try/catch for async operations
- Log errors with `console.error`
- Set appropriate error states in UI

```typescript
const handleAction = async () => {
  try {
    setIsLoading(true);
    const result = await someAsyncFunction();
    setResult(result);
  } catch (e) {
    console.error(e);
    setError('Failed to perform action');
  } finally {
    setIsLoading(false);
  }
};
```

### Tailwind CSS
- Use Tailwind utility classes for all styling
- Follow consistent spacing scale (p-4, m-2, gap-6, etc.)
- Use semantic color names (slate-800, blue-600, etc.)
- Use `clsx` or `tailwind-merge` for conditional classes

### 3D Rendering (React Three Fiber)
- Use `@react-three/fiber` for Canvas
- Use `@react-three/drei` for helpers (OrbitControls, Environment, etc.)
- Memoize expensive 3D computations with `useMemo`
- Use `key` prop on repeated 3D elements

---

## Project Structure

```
/home/nraatika/projects/evo
├── App.tsx                 # Main application component
├── index.tsx              # Entry point
├── components/
│   ├── Scene3D.tsx       # 3D tree renderer (React Three Fiber)
│   ├── ControlPanel.tsx  # Sidebar controls
│   ├── Gallery.tsx        # Scene gallery display
│   └── DetailModal.tsx   # Scene detail view
├── services/
│   └── mockBackend.ts    # Tree generation & genetic algorithm
├── types.ts              # TypeScript interfaces
├── vite.config.ts         # Vite configuration
└── package.json
```

---

## Key Technologies

- **React 19** - UI framework
- **TypeScript** - Type safety
- **Vite** - Build tool
- **Tailwind CSS** - Styling
- **React Three Fiber** - 3D rendering
- **Recharts** - Charts (if used)
- **Lucide React** - Icons

---

## Common Development Tasks

### Adding a new component
1. Create file in `components/` with PascalCase name
2. Define props interface
3. Export as named export using `React.FC`
4. Import and use in parent component

### Adding new types
1. Add interface/type to `types.ts`
2. Export for use across the app
3. Use path alias `@/types` for imports

### Running lint before committing
```bash
npm run lint
# Fix any issues before committing
```

---

## Configuration Files

- **tsconfig.json**: TypeScript config with `@/*` path alias, ES2022 target
- **vite.config.ts**: Vite with React plugin, path alias, dev server on port 3000
- **package.json**: Dependencies and npm scripts

---

## Notes for AI Agents

- Backend API runs on FastAPI at `http://localhost:8000`
- Frontend calls backend endpoints instead of using mock functions
- API keys (if any) are loaded from environment variables via Vite

### Planned Enhancements

- **Validation**: Generate scenes button should show error when no reference image is provided (currently no validation for missing `targetImage` input)
