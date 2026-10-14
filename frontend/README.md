# Frontend: Angular Storefront

An Angular single-page storefront for the commerce APIs. The UI includes authentication screens, a home/catalog view, cart and order pages, shared layout components, and API services/interceptors.

## Stack

- Angular 16 and TypeScript
- Angular Material for UI components
- Tailwind CSS for utility-based styling
- Angular Router and RxJS for navigation and asynchronous API calls

## Run locally

Start the backend API Gateway on port `8888`, then run:

```bash
cd frontend
npm ci
npm start
```

Open `http://localhost:4200`. The development server forwards requests under `/api` to `http://localhost:8888` using `proxy.conf.json`.

## Production build

```bash
npm run build
```

The Angular CLI writes the static build output to `dist/`. The included `Dockerfile` and `nginx.conf` provide the container-serving path.

## Source layout

- `src/app/authentication/` — login, signup, and guards
- `src/app/pages/` — home, cart, and order views
- `src/app/components/` — shared header, footer, and fallback page
- `src/app/services/` — API integration and interceptors
