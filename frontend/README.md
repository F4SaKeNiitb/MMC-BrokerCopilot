# Broker Copilot - Frontend

AI-augmented workflow platform for insurance brokers. Built with Next.js 14, React 18, and Tailwind CSS.

## Features

- **Dashboard** - Overview of renewal pipeline with stats and quick actions
- **Renewals Pipeline** - Kanban/list view with priority scoring and filtering
- **One-Page Briefs** - Streaming AI-generated briefs with citations
- **Copilot Chat** - Connector-backed Q&A with function-calling
- **Connections** - OAuth integration for Microsoft 365, Salesforce, HubSpot
- **Settings** - User preferences and configuration

## Getting Started

### Prerequisites

- Node.js 18+
- Backend server running on `http://localhost:8000`

### Installation

```bash
cd frontend
npm install
```

### Development

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

### Production Build

```bash
npm run build
npm start
```

## Architecture

### Tech Stack

- **Framework**: Next.js 14 (App Router)
- **UI**: React 18 + Tailwind CSS
- **Icons**: Lucide React
- **Date Handling**: date-fns
- **Type Safety**: TypeScript 5

### Project Structure

```
src/
├── app/                    # Next.js App Router pages
│   ├── page.tsx           # Dashboard
│   ├── renewals/          # Renewals pipeline
│   ├── chat/              # Copilot chat
│   ├── connections/       # OAuth connections
│   └── settings/          # User settings
├── components/
│   ├── ui/                # Reusable UI components
│   ├── layout/            # App layout
│   ├── renewals/          # Renewal-specific components
│   ├── brief/             # Brief modal
│   ├── chat/              # Chat interface
│   └── connections/       # Connection manager
└── lib/
    ├── api.ts             # API client with streaming support
    ├── types.ts           # TypeScript interfaces
    └── utils.ts           # Utility functions
```

### API Integration

The frontend proxies all API calls through Next.js rewrites:

```
/api/* → http://localhost:8000/*
```

This keeps the backend URL configuration in one place and avoids CORS issues.

### Streaming Support

The app supports streaming responses for:
- One-page briefs (`/brief/{policy_id}`)
- Chat responses (`/chat/stream`)

Streaming provides better UX by showing content as it's generated.

## Design Principles

1. **Zero State** - No business data stored locally
2. **Real-time** - All data fetched live from backend
3. **Transparency** - Every AI fact linked to source
4. **Mobile First** - Responsive design throughout

## Available Scripts

- `npm run dev` - Start development server
- `npm run build` - Build for production
- `npm start` - Start production server
- `npm run lint` - Run ESLint

