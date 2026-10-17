# PatchHive Architecture

> Canonical alignment notice: the authoritative MVP is a FastAPI/React modular monolith with pure domain code in `backend/canon`, persistence adapters in `backend/canon/models.py` and `repository.py`, and historical social/publishing routes disabled by default. See [Canon alignment](CANON_ALIGNMENT.md). Statements below describing older surfaces are retained as historical detail where they conflict.

This document describes the high-level architecture of PatchHive and how the different components interact.

## Overview

PatchHive follows a modular monorepo architecture with clear separation between backend, frontend, and shared concerns. The system is designed around the Eurorack modular synthesis mental model: modules, cases, racks, patches, and signals.

## System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                      Frontend (React)                    │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐ │
│  │  Pages   │  │Components│  │   State  │  │   API   │ │
│  │          │  │          │  │ (Zustand)│  │ Client  │ │
│  └──────────┘  └──────────┘  └──────────┘  └─────────┘ │
└─────────────────────────────────────────────────────────┘
                           │
                           │ HTTP/JSON
                           ▼
┌─────────────────────────────────────────────────────────┐
│                   Backend API (FastAPI)                  │
│  ┌──────────────────────────────────────────────────┐   │
│  │                  Route Handlers                   │   │
│  │  Modules │ Cases │ Racks │ Patches │ Community   │   │
│  └──────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────┐   │
│  │               Business Logic Layer                │   │
│  │  • Validation    • Patch Engine   • Export       │   │
│  │  • Naming        • Visualization  • Ingest       │   │
│  └──────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────┐   │
│  │               Data Access Layer                   │   │
│  │           SQLAlchemy ORM + Pydantic              │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
                    ┌──────────────┐
                    │  PostgreSQL  │
                    │   Database   │
                    └──────────────┘
```

## Backend Architecture

### Domain Organization

The backend is organized into domains, each with clear responsibilities:

#### 1. **Core** (`backend/core/`)
- **Purpose**: Foundational utilities shared across domains
- **Components**:
  - `config.py`: Application configuration using Pydantic settings
  - `database.py`: SQLAlchemy engine and session management
  - `security.py`: Authentication, password hashing, JWT tokens
  - `naming.py`: Deterministic name generation for racks and patches

#### 2. **Modules** (`backend/modules/`)
- **Purpose**: Eurorack module catalog management
- **Components**:
  - `models.py`: Module SQLAlchemy model
  - `schemas.py`: Pydantic schemas for validation
  - `routes.py`: CRUD API endpoints
- **Key Features**:
  - Full module metadata (brand, HP, power, I/O ports)
  - Tagging and categorization
  - Data provenance tracking (source, import timestamp)

#### 3. **Cases** (`backend/cases/`)
- **Purpose**: Eurorack case catalog management
- **Components**: Similar to Modules domain
- **Key Features**:
  - Multi-row layout support
  - Power supply specifications
  - HP capacity per row

#### 4. **Racks** (`backend/racks/`)
- **Purpose**: User rack configurations and validation
- **Components**:
  - `models.py`: Rack and RackModule models
  - `schemas.py`: Request/response schemas
  - `routes.py`: Rack CRUD and retrieval
  - `validation.py`: HP and power validation logic
- **Key Features**:
  - Module placement validation
  - Deterministic naming
  - Public/private sharing

#### 5. **Patches** (`backend/patches/`)
- **Purpose**: Patch generation, storage, and management
- **Components**:
  - `models.py`: Patch model with connection graph
  - `schemas.py`: Patch schemas
  - `routes.py`: Patch CRUD and generation endpoint
  - `engine.py`: **Deterministic patch generation engine**
- **Key Features**:
  - Rule-based patch generation
  - Connection graph representation
  - Category detection (Voice/Modulation/Clock-Rhythm/etc.)
  - Full provenance (seed, version, config)

#### 6. **Community** (`backend/community/`)
- **Purpose**: Users, authentication, social features
- **Components**:
  - `models.py`: User, Vote, Comment models
  - `schemas.py`: Auth and social schemas
  - `routes.py`: Auth, profile, voting, commenting, feed
- **Key Features**:
  - JWT-based authentication
  - Voting/favoriting
  - Comments
  - Public feed

#### 7. **Export** (`backend/export/`)
- **Purpose**: Visualization and PDF generation
- **Components**:
  - `visualization.py`: SVG rack layout and patch diagram generators
  - `waveform.py`: SVG **symbolic** waveform approximation generator (not audio DSP)
  - `pdf.py`: PDF patch book generator using ReportLab
  - `routes.py`: Export endpoints
- **Key Features**:
  - Deterministic symbolic waveform thumbnails from patch category
  - Color-coded module types (color is never the only cable signal)
  - Multi-page PDF patch books (one-page publishing invariant for 0.3.x)

#### 8. **Ingest** (`backend/ingest/`)
- **Purpose**: External data import
- **Components**:
  - `modulargrid.py`: ModularGrid adapter (interface only, implementation pending)
- **Design**: Pluggable adapters for different data sources

#### 8b. **Evidence & Visual System Intelligence** (`backend/evidence/`, `backend/canon/`)
- **Purpose**: Photo/manual/hybrid system intake without provider authority
- **Components**:
  - `evidence/images.py`: secure re-encode, MIME sniffing, local quality gates
  - `evidence/vision_provider.py`: provider-neutral `VisionEvidenceProvider` (+ mock/fixture)
  - `canon/visual_contracts.py`: candidates, confirmations, inventory, capability graph
  - `canon/inventory.py`: immutable inventory revision + confirmed-hardware patch gates
  - `canon/runes.py`: `detect_modules` rejects self-confirmed provider evidence
- **Trust boundary**: Image → untrusted evidence → user confirmation → immutable inventory → deterministic generation
- **Out of scope**: audio capture/analysis/DSP, hardware control, live model dependence in CI

### Database Schema

Key relationships:
- `User` → `Rack` (one-to-many)
- `Case` → `Rack` (one-to-many)
- `Module` → `RackModule` (one-to-many)
- `Rack` → `RackModule` (one-to-many)
- `Rack` → `Patch` (one-to-many)
- `User` → `Vote`, `Comment` (one-to-many)
- `Rack`, `Patch` → `Vote`, `Comment` (one-to-many)

See [DATA_MODEL.md](DATA_MODEL.md) for full schema details.

## Frontend Architecture

### Component Organization

```
src/
├── components/     # Reusable UI components (future)
├── pages/          # Page components (one per route)
│   ├── Home.tsx
│   ├── Modules.tsx
│   ├── Cases.tsx
│   ├── Racks.tsx
│   ├── RackBuilder.tsx
│   ├── Patches.tsx
│   ├── Feed.tsx
│   └── Login.tsx
├── lib/            # Core logic
│   ├── api.ts      # API client with typed endpoints
│   └── store.ts    # Zustand state management
└── types/
    └── api.ts      # TypeScript types matching backend schemas
```

### State Management

- **Zustand** for global state (auth, user)
- **React hooks** for component-local state
- **API client** with Axios for backend communication

### Routing

- **React Router** for SPA navigation
- Protected routes for authenticated actions
- Public pages for browsing shared content

## Communication Flow

### Example: Generating Patches for a Rack

1. **Frontend**: User clicks "Generate Patches" on a rack
2. **Frontend**: Calls `patchApi.generate(rackId, { seed: 42, max_patches: 10 })`
3. **Backend**: `POST /api/patches/generate/{rack_id}`
4. **Backend**: Route handler calls `patches/engine.py::generate_patches_for_rack()`
5. **Patch Engine**:
   - Analyzes modules in rack (VCOs, VCFs, VCAs, etc.)
   - Generates patch specifications based on rules
   - Uses deterministic Random with provided seed
   - Returns list of `PatchSpec` objects
6. **Backend**: Saves patches to database with full metadata
7. **Backend**: Returns generated patches as JSON
8. **Frontend**: Displays patches in UI, allows viewing diagrams and exporting

## Deployment Architecture

### Docker Compose Stack

```yaml
services:
  db:          # PostgreSQL database
  backend:     # FastAPI application
  frontend:    # Vite dev server (dev) or Nginx (prod)
```

### Environment Configuration

- Backend: Environment variables via `.env` or container env
- Frontend: Build-time environment variables via Vite
- Database: Connection string configured in backend

### Scaling Considerations

- Backend is stateless and can be horizontally scaled
- Database can be scaled with read replicas
- Frontend can be served from CDN in production
- File exports can be moved to object storage (S3, etc.)

## ABX-Core v1.2 Compliance

### Modularity
- Clean domain boundaries with minimal coupling
- Each domain has its own models, schemas, and routes
- Core utilities factored into shared module

### Determinism
- Patch generation uses seeded Random instances
- Same seed + rack = same patches every time
- No hidden randomness or entropy sources

### SEED Enforcement
- All data imports tracked with source and timestamp
- Patch generation stores seed, version, and config
- Full provenance chain for reproducibility

### Eurorack Mental Model
- Domain language matches Eurorack terminology
- Data structures mirror physical modular concepts
- Patch engine follows signal flow principles

See [ABX_CORE_COMPLIANCE.md](ABX_CORE_COMPLIANCE.md) for detailed compliance documentation.

## Future Architecture Enhancements

### Phase 2
- **Real-time collaboration**: WebSocket layer for multi-user rack editing
- **Caching layer**: Redis for frequently accessed data
- **Job queue**: Celery for async patch generation and exports

### Phase 3
- **Microservices**: Split export/visualization into separate service
- **GraphQL**: Alternative API for more efficient data fetching
- **Event sourcing**: Full audit trail of all system changes


## Decision Intelligence boundary (specified 2026-09-25)

Decision Intelligence is an evidence-side subsystem, not part of canonical authority. Normalized vision/OCR/retrieval evidence may be sent to a provider-neutral `DecisionProvider`; its immutable `DecisionPacket` is evaluated by a deterministic, versioned `DecisionPolicy`. The result is a proposal, review requirement, unresolved state, rejection, or bounded escalation. Existing confirmation/application services remain the only path from probabilistic evidence to canonical inventory.

Jev is a planned adapter behind this contract. Canonical packages MUST NOT import Jev-specific types. See [`specs/005-decision-intelligence/`](../specs/005-decision-intelligence/spec.md) and [DECISION_INTELLIGENCE.md](DECISION_INTELLIGENCE.md).
