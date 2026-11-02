# Publishing API Contract (historical, feature-flagged)

> This surface is outside the canonical MVP. It is disabled unless `ENABLE_LEGACY_PUBLISHING=true`, is absent from active navigation, and must not be represented as a current product capability.

Base URL: `/api`

## Authenticated Endpoints

### POST `/me/exports`
Create export artifacts for a patch or rack.

**Request**
```json
{
  "source_type": "patch",
  "source_id": 123
}
```

**Response**
```json
{
  "id": 1,
  "export_type": "patch",
  "license": "CC BY-NC 4.0",
  "run_id": "uuid",
  "generated_at": "2024-01-01T00:00:00Z",
  "patch_count": 1,
  "manifest_hash": "hash",
  "artifact_urls": {
    "pdf": "...",
    "svg": "...",
    "zip": "...",
    "waveform_svg": "..."
  }
}
```

### GET `/me/exports`
List exports for current user.

### POST `/me/publications`
Create publication for an export.

**Request**
```json
{
  "export_id": 1,
  "title": "Publication title",
  "description": "Optional description",
  "visibility": "public",
  "allow_download": true,
  "allow_remix": false,
  "cover_image_url": "https://..."
}
```

**Response**
```json
{
  "id": 1,
  "export_id": 1,
  "slug": "publication-title-abcdef12",
  "visibility": "public",
  "status": "published",
  "allow_download": true,
  "allow_remix": false,
  "title": "Publication title",
  "description": "Optional description",
  "cover_image_url": "https://...",
  "published_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

### PATCH `/me/publications/{publication_id}`
Owner-only updates. Allowed fields: `title`, `description`, `visibility`, `allow_download`, `allow_remix`, `cover_image_url`, `status` (`published` | `hidden`).

### GET `/me/publications`
List publications for current user.

**Response**
```json
{
  "publications": [
    {
      "id": 1,
      "export_id": 1,
      "slug": "publication-title-abcdef12",
      "visibility": "public",
      "status": "published",
      "allow_download": true,
      "allow_remix": false,
      "title": "Publication title",
      "description": "Optional description",
      "cover_image_url": "https://...",
      "published_at": "2024-01-01T00:00:00Z",
      "updated_at": "2024-01-01T00:00:00Z"
    }
  ]
}
```

## Public Read Endpoints

### GET `/p/{slug}`
Read-only publication data.

**Response**
```json
{
  "title": "Publication title",
  "description": "Optional description",
  "cover_image_url": "https://...",
  "export_type": "patch",
  "license": "CC BY-NC 4.0",
  "provenance": {
    "run_id": "uuid",
    "generated_at": "2024-01-01T00:00:00Z",
    "patch_count": 1,
    "manifest_hash": "hash"
  },
  "publisher_display": "PatchHive User",
  "avatar_url": null,
  "allow_download": true,
  "download_urls": {
    "pdf_url": "/api/p/slug/download/pdf",
    "svg_url": "/api/p/slug/download/svg",
    "zip_url": "/api/p/slug/download/zip"
  }
}
```

### GET `/p/{slug}/download/{artifact_type}`
Serve the artifact (`pdf` | `svg` | `zip`) if `allow_download` is true.

### GET `/gallery/publications`
Public gallery listing.

**Query Params**
- `limit` (1-50)
- `cursor` (ISO datetime)
- `export_type` (`patch` | `rack`)
- `recent_days` (1-365)

**Response**
```json
{
  "publications": [
    {
      "slug": "publication-title-abcdef12",
      "title": "Publication title",
      "description": "Optional description",
      "cover_image_url": "https://...",
      "export_type": "patch",
      "published_at": "2024-01-01T00:00:00Z"
    }
  ],
  "next_cursor": "2024-01-01T00:00:00Z"
}
```

### POST `/p/{slug}/report`
Report a publication.

**Request**
```json
{
  "reason": "Reason text",
  "details": "Optional details"
}
```

Anonymous reports are accepted. Each client address may send 10 reports an hour (429 `REPORT_RATE_LIMIT` after that). A signed-in reporter who already reported the publication gets 200 `{"status": "already_reported"}` and no new report is stored.

## Admin Moderation

### POST `/admin/publications/{publication_id}/hide`
Hide a publication. Requires admin privileges. Writes audit log.

### POST `/admin/publications/{publication_id}/remove`
Remove a publication. Requires admin privileges. Writes audit log.

**Request**
```json
{
  "reason": "Moderation reason"
}
```
