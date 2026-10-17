/**
 * Legacy / feature-flagged client surfaces (not used by App.tsx MVP routes).
 * Kept for historical pages under src/legacy/pages only.
 */
import api from "@/lib/api";
import type {
  FeedResponse,
  ExportRecord,
  PublicationListResponse,
  PublicationRecord,
  PublicPublicationResponse,
  GalleryResponse,
  LeaderboardEntry,
} from "@/types/api";

export const communityApi = {
  getFeed: (params?: { skip?: number; limit?: number }) =>
    api.get<FeedResponse>("/community/feed", { params }),

  vote: (data: { rack_id?: number; patch_id?: number }) => api.post("/community/votes", data),

  deleteVote: (voteId: number) => api.delete(`/community/votes/${voteId}`),

  comment: (data: { rack_id?: number; patch_id?: number; content: string }) =>
    api.post("/community/comments", data),

  getComments: (params: { rack_id?: number; patch_id?: number }) =>
    api.get("/community/comments", { params }),
};

export const publishingApi = {
  createExport: (data: { source_type: "patch" | "rack"; source_id: number }) =>
    api.post<ExportRecord>("/me/exports", data),

  listExports: () => api.get<ExportRecord[]>("/me/exports"),

  createPublication: (data: {
    export_id: number;
    title: string;
    description?: string;
    visibility: "public" | "unlisted";
    allow_download: boolean;
    allow_remix: boolean;
    cover_image_url?: string;
  }) => api.post<PublicationRecord>("/me/publications", data),

  updatePublication: (publicationId: number, data: Partial<PublicationRecord>) =>
    api.patch<PublicationRecord>(`/me/publications/${publicationId}`, data),

  listPublications: () => api.get<PublicationListResponse>("/me/publications"),

  getPublication: (slug: string) => api.get<PublicPublicationResponse>(`/p/${slug}`),

  listGallery: (params?: {
    limit?: number;
    cursor?: string;
    export_type?: string;
    recent_days?: number;
  }) => api.get<GalleryResponse>("/gallery/publications", { params }),

  reportPublication: (slug: string, data: { reason: string; details?: string }) =>
    api.post(`/p/${slug}/report`, data),
};

export const leaderboardsApi = {
  getPopularModules: () => api.get<LeaderboardEntry[]>("/leaderboards/modules/popular"),
  getTrendingModules: (windowDays = 30) =>
    api.get<LeaderboardEntry[]>("/leaderboards/modules/trending", {
      params: { window_days: windowDays },
    }),
};
