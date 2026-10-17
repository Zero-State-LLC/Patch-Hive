# Legacy frontend surfaces

Unrouted MVP-excluded pages and clients. **Not imported by `App.tsx`.**

| Path                            | Former product surface                               |
| ------------------------------- | ---------------------------------------------------- |
| `pages/Feed.tsx`                | Community feed                                       |
| `pages/Publish.tsx`             | Publishing wizard                                    |
| `pages/Publication.tsx`         | Public publication                                   |
| `pages/Gallery.tsx`             | Publication gallery                                  |
| `pages/LeaderboardsModules.tsx` | Module leaderboards                                  |
| `apiClients.ts`                 | `communityApi` / `publishingApi` / `leaderboardsApi` |

Backend routers remain behind `ENABLE_LEGACY_*` flags. Do not re-link these pages without flag review and a product decision.
