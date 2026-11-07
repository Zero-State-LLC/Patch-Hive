## Module Catalog Architecture

**Two-Tier Design for Scalability**

### Problem

ModularGrid has **8,000+ modules**. Storing full specs for all modules is:
- Storage intensive (I/O ports, power, tags, descriptions)
- Slow to query (complex JSON fields)
- Wasteful (most modules never used)

### Solution: Catalog + Specs

**Tier 1: Module Catalog** (Lightweight, Complete)
- **All** modules from ModularGrid (~8,000+)
- **Minimal** data: brand, name, HP, category, image
- **Fast** search/filter/sort
- **Browseable** catalog for discovery

**Tier 2: Full Module Specs** (Heavy, On-Demand)
- **Only** modules user adds to rack
- **Complete** specs: I/O ports, power, tags, manuals
- **Cached** in user profile
- **Lazy-loaded** when needed

---

## Data Flow

### 1. Browse Catalog (Fast)

User searches for "filter":

```
GET /api/modules/catalog?search=filter&category=VCF

Returns: [
  {
    "slug": "mutable-instruments-ripples",
    "brand": "Mutable Instruments",
    "name": "Ripples",
    "hp": 8,
    "category": "VCF",
    "image_url": "...",
    "is_available": "available"
  },
  ...
]
```

**Performance**: <100ms for 8,000 modules (indexed queries)

### 2. View Details (Medium)

User clicks on "Ripples":

```
GET /api/modules/catalog/mutable-instruments-ripples

Returns: {
  // Same lightweight catalog data
  "slug": "mutable-instruments-ripples",
  "brand": "Mutable Instruments",
  ...
}
```

**Note**: Still lightweight! Full specs not loaded yet.

### 3. Add to Rack (Heavy)

User adds "Ripples" to their rack:

```
POST /api/racks/123/modules
{
  "catalog_slug": "mutable-instruments-ripples",
  "position_hp": 0,
  "row": 0
}
```

**Backend Flow**:
1. Check if full specs exist in `modules` table
2. If not → fetch from ModularGrid API or pre-loaded data
3. Create `Module` record with full specs
4. Link to user's rack
5. Cache for future use

**Performance**: First add: ~500ms (fetch specs). Subsequent: <50ms (cached).

---

## Database Schema

### `module_catalog` (Lightweight)

```sql
CREATE TABLE module_catalog (
  id INTEGER PRIMARY KEY,
  modulargrid_id INTEGER UNIQUE,  -- ModularGrid ID
  slug VARCHAR(200) UNIQUE,        -- brand-name
  brand VARCHAR(100),
  name VARCHAR(200),
  hp INTEGER,
  category VARCHAR(50),            -- VCO, VCF, etc.
  image_url VARCHAR(500),
  modulargrid_url VARCHAR(500),
  manufacturer_url VARCHAR(500),
  is_available VARCHAR(20),        -- available/discontinued/upcoming
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);

-- Indexes for fast filtering
CREATE INDEX idx_catalog_brand_name ON module_catalog(brand, name);
CREATE INDEX idx_catalog_category_hp ON module_catalog(category, hp);
CREATE INDEX idx_catalog_available ON module_catalog(is_available);
```

**Size**: ~8,000 rows × 500 bytes = ~4 MB

### `modules` (Full Specs)

```sql
CREATE TABLE modules (
  id INTEGER PRIMARY KEY,
  catalog_id INTEGER REFERENCES module_catalog(id),  -- Link to catalog
  brand VARCHAR(100),
  name VARCHAR(200),
  hp INTEGER,
  module_type VARCHAR(50),

  -- Heavy fields
  power_12v_ma INTEGER,
  power_neg12v_ma INTEGER,
  power_5v_ma INTEGER,
  io_ports JSON,                   -- Full I/O specification
  tags JSON,
  description TEXT,

  -- Provenance
  source VARCHAR(50),
  source_reference VARCHAR(500),
  imported_at TIMESTAMP,

  created_at TIMESTAMP,
  updated_at TIMESTAMP
);
```

**Size**: Only modules users actually use (sparse population)

---

## API Endpoints

### Catalog Browsing

**Search/Filter**
```
GET /api/modules/catalog
  ?search=filter
  &brand=Mutable+Instruments
  &category=VCF
  &hp_min=6
  &hp_max=12
  &sort_by=hp
  &sort_order=asc
  &skip=0
  &limit=50
```

**List Brands**
```
GET /api/modules/catalog/brands

Returns: [
  {"name": "Mutable Instruments", "module_count": 127},
  {"name": "Make Noise", "module_count": 89},
  ...
]
```

**List Categories**
```
GET /api/modules/catalog/categories

Returns: [
  {"name": "VCO", "module_count": 1234},
  {"name": "VCF", "module_count": 567},
  ...
]
```

**Get Catalog Entry**
```
GET /api/modules/catalog/{slug}

Returns: {
  "slug": "mutable-instruments-plaits",
  "brand": "Mutable Instruments",
  "name": "Plaits",
  "hp": 12,
  "category": "VCO",
  ...
}
```

**Catalog Stats**
```
GET /api/modules/catalog/stats

Returns: {
  "total_modules": 8234,
  "total_brands": 523,
  "total_categories": 15,
  "hp_stats": {
    "average": 12.3,
    "min": 2,
    "max": 84
  }
}
```

### Full Specs (Existing)

```
GET /api/modules/{id}        # Full specs for specific module
GET /api/modules/             # List modules with full specs
```

---

## Population Strategy

### Loading the catalog

`data/synth-catalog/population.py` is the only writer of catalog rows (spec 003 D5). Run a dry run first, then apply with the hashes it printed, through `.github/workflows/db-load.yml`. Locally, use `scripts/import_catalog_population.py`.

## Benefits

### Performance

- **Catalog browsing**: <100ms (indexed lightweight queries)
- **Search**: <200ms (full-text on brand/name)
- **Filter**: <150ms (multi-column indexes)
- **Full specs**: Only loaded when needed

### Storage

- **Catalog**: ~4 MB for 8,000 modules
- **Full specs**: Only what users actually use
- **Example**: 100 users × 50 modules each = 5,000 module specs vs 8,000

### Scalability

- Can handle **all** ModularGrid modules (8,000+)
- Room for growth (new modules daily)
- No performance degradation

### User Experience

- Fast catalog browsing
- Search/filter works across all modules
- Details loaded on-demand
- No waiting for unused data

---

## Migration Path

### Existing 32 Modules

Our current 32 modules with full specs can be:

**Option A**: Keep in `modules` table, also add to catalog
- Catalog has lightweight entry
- Module table has full specs
- Best of both worlds

**Option B**: Migrate to catalog-first
- Move to catalog
- Fetch full specs on first rack add
- Cleaner separation

**Recommendation**: Option A (backward compatible)

---

## Example Queries

### "Find all filters under 10HP"

```sql
SELECT * FROM module_catalog
WHERE category = 'VCF' AND hp < 10
ORDER BY hp ASC;
```

**Fast**: Indexed on category + hp

### "Search for 'Maths'"

```sql
SELECT * FROM module_catalog
WHERE brand LIKE '%Maths%' OR name LIKE '%Maths%';
```

**Fast**: Indexed on brand + name

### "Most popular brands"

```sql
SELECT brand, COUNT(*) as module_count
FROM module_catalog
GROUP BY brand
ORDER BY module_count DESC
LIMIT 20;
```

---

## Future Enhancements

### 1. User Ratings

```sql
ALTER TABLE module_catalog
ADD COLUMN avg_rating DECIMAL(3,2),
ADD COLUMN rating_count INTEGER;
```

### 2. Price Tracking

```sql
CREATE TABLE module_prices (
  id INTEGER PRIMARY KEY,
  catalog_id INTEGER REFERENCES module_catalog(id),
  vendor VARCHAR(100),
  price_usd DECIMAL(10,2),
  currency VARCHAR(3),
  in_stock BOOLEAN,
  updated_at TIMESTAMP
);
```

### 3. Alternatives/Similar

```sql
CREATE TABLE module_alternatives (
  module_id INTEGER REFERENCES module_catalog(id),
  alternative_id INTEGER REFERENCES module_catalog(id),
  similarity_score DECIMAL(3,2),
  reason VARCHAR(200)  -- "Similar functionality", "Same HP", etc.
);
```

### 4. Patch Compatibility

```sql
CREATE TABLE module_compatibility (
  module_a INTEGER REFERENCES module_catalog(id),
  module_b INTEGER REFERENCES module_catalog(id),
  compatibility_score DECIMAL(3,2),
  patch_count INTEGER  -- How many users patch these together
);
```

---

## Implementation Status

- [x] ModuleCatalog model
- [x] Catalog API endpoints (search/filter/sort)
- [x] Catalog populator (curated + CSV import)
- [x] Documentation
- [ ] UI integration (search/browse interface)
- [ ] Lazy-load full specs on rack add
- [ ] ModularGrid API integration (if available)
- [ ] User-contributed catalog additions

---

**Version**: 1.0
**Date**: 2025-12-05
**Status**: Ready for testing
