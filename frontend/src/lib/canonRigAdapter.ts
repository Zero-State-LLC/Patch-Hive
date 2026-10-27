/**
 * Spec 008 T020: F5 inventory list cutover adapter.
 *
 * Maps canon rig DTOs (GET /api/canon/rigs, GET /api/canon/rigs/{rig_id}) onto the
 * existing Rack view type so list pages read the canonical path while writes stay
 * on rackApi. rig_id is identical to rack.id (F2 alias).
 */
import type { Rack, RackModule } from "@/types/api";

export interface CanonRigSummaryDto {
  rig_id: number;
  rack_id: number;
  user_id: number;
  case_id: number;
  name: string | null;
  name_suggested: string | null;
  description: string | null;
  tags: string[];
  is_public: boolean;
  module_count: number;
  created_at: string;
  updated_at: string;
}

export interface CanonRigDetailDto extends CanonRigSummaryDto {
  generation_seed: number | null;
  modules: Array<Record<string, unknown>>;
  case: Record<string, unknown> | null;
  vote_count: number;
}

/** List rows carry no placements; modules stay empty until the detail is loaded. */
export function rigSummaryToRack(rig: CanonRigSummaryDto): Rack {
  return {
    id: rig.rig_id,
    user_id: rig.user_id,
    case_id: rig.case_id,
    name: rig.name ?? "",
    name_suggested: rig.name_suggested ?? undefined,
    description: rig.description ?? undefined,
    tags: rig.tags ?? [],
    is_public: rig.is_public,
    created_at: rig.created_at,
    updated_at: rig.updated_at,
    // Canon list rows do not carry votes; the detail mapping fills the real count.
    vote_count: 0,
    modules: [],
  };
}

/** Detail rows carry the same placements and case payload as GET /api/racks/{id}. */
export function rigDetailToRack(rig: CanonRigDetailDto): Rack {
  return {
    ...rigSummaryToRack(rig),
    generation_seed: rig.generation_seed ?? undefined,
    modules: (rig.modules ?? []) as unknown as RackModule[],
    case: (rig.case ?? undefined) as unknown as Rack["case"],
    vote_count: rig.vote_count ?? 0,
  };
}
