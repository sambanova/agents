# Next.js Migration for Agent Crew

This project is a migration of the Vue.js-based Agent Crew frontend to Next.js. The migration preserves the core functionality while adapting the architecture to Next.js and React patterns.

## Project Structure

- `/app`: Next.js app router pages and layouts
- `/components`: Reusable React components 
- `/lib`: Utility functions, API client, and state management
- `/public`: Static assets
- `/styles`: Global CSS styles

## Key Features

- Chat-based interface for conversational AI interactions
- Workflow mode for structured research and analysis
- Document upload and management
- Financial analysis and research reports
- Agent thought visualization for transparency

## Differences from Vue.js Version

- Uses Next.js App Router for routing instead of Vue Router
- Uses Zustand for state management instead of Pinia
- Uses React components instead of Vue components
- Authentication handled by external system (via `hasAccessToken()`)
- WebSocket management adapted for React patterns

## Getting Started

1. Install dependencies:
   ```bash
   npm install
   ```

2. Run the development server:
   ```bash
   npm run dev
   ```

3. Build for production:
   ```bash
   npm run build
   ```

## Integrating with Your Next.js Project

To use this code in your existing Next.js project:

1. Copy the `/components`, `/lib`, and `/styles` directories to your project
2. Copy the `/app` directory files as needed
3. Update your tailwind.config.js to include the custom theme settings
4. Add the required dependencies to your package.json
5. Adjust authentication to work with your existing system

## Environment Variables

- `NEXT_PUBLIC_API_URL`: URL for the backend API (defaults to http://localhost:8000)
- `NEXT_PUBLIC_WEBSOCKET_URL`: URL for WebSocket connections (defaults to ws://localhost:8000)

These variables are set in the `.env.local` file for development. For production, you should set these environment variables in your deployment environment.

## API Routing

The application is configured to route API requests through Next.js's API routes. All API requests use the path `/api/python/:path*`, which is rewritten to the backend API at `NEXT_PUBLIC_API_URL/:path*`.

When making direct fetch or axios calls, use the path `/api/python/your-endpoint`. The API client in `lib/api.ts` is already configured to use this base URL.

## Authentication

The authentication implementation is a placeholder. Replace the functions in `/lib/auth.ts` with your own authentication system.

## State Management

Zustand is used for state management. The main store is in `/lib/store.ts`, which replaces the Pinia store from the Vue.js version.