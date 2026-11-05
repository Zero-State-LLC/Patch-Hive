import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import type { ModuleToPlace } from "@/lib/api";
import EvidenceStep, { type FusionView, type ReviewCandidate } from "./EvidenceStep";

const candidates: ReviewCandidate[] = [
  {
    id: "c1",
    label: "Oscillator A",
    manufacturer: "Sim",
    confidence: 0.8,
    alternatives: [],
    status: "inferred",
    moduleRevisionId: "rev-1",
  },
];

function fusion(overrides: Partial<FusionView> = {}): FusionView {
  return {
    entities: [],
    applied: {},
    feedback: null,
    status: null,
    note: null,
    imageCount: 0,
    onApply: vi.fn(),
    onConfirmAll: vi.fn(),
    ...overrides,
  };
}

function renderReview(props: {
  fromLiveApi: boolean;
  fusion: FusionView;
  targetRackId?: number | null;
  revisionId?: string | null;
  readyForGeneration?: boolean;
  modulesToPlace?: ModuleToPlace[];
}) {
  return render(
    <MemoryRouter>
      <EvidenceStep
        rackChoices={null}
        selectedRackId={null}
        onSelectRack={vi.fn()}
        targetRackId={null}
        state="review"
        error=""
        fileLabel="rig.jpg"
        pendingCount={1}
        onSelectPhotos={vi.fn()}
        onDetect={vi.fn()}
        candidates={candidates}
        onSetStatus={vi.fn()}
        confirmedCount={0}
        allResolved={false}
        onCreateRevision={vi.fn()}
        revisionId={null}
        readyForGeneration={false}
        modulesToPlace={[]}
        {...props}
      />
    </MemoryRouter>,
  );
}

describe("EvidenceStep review", () => {
  it("labels the built-in candidates as a demo", () => {
    renderReview({ fromLiveApi: false, fusion: fusion({ status: "DEMO_SINGLE" }) });
    expect(screen.getByText("Demo", { selector: ".status-chip" })).toBeInTheDocument();
    expect(screen.getByText(/these were not detected from your photos/)).toBeInTheDocument();
    expect(screen.getByText(/^Status: Demo, one photo/)).toBeInTheDocument();
  });

  it("drops the demo label for candidates detected from the user's photos", () => {
    renderReview({ fromLiveApi: true, fusion: fusion() });
    expect(screen.queryByText("Demo", { selector: ".status-chip" })).not.toBeInTheDocument();
  });

  it("reads reconcile status codes as words, unknown ones included", () => {
    const { unmount } = renderReview({
      fromLiveApi: true,
      fusion: fusion({ status: "RECONCILED_WITH_CONFLICTS", imageCount: 2 }),
    });
    expect(screen.getByText("Status: Reconciled, with conflicts, 2 images")).toBeInTheDocument();
    unmount();
    renderReview({ fromLiveApi: true, fusion: fusion({ status: "PARTIAL_MATCH" }) });
    expect(screen.getByText("Status: Partial match")).toBeInTheDocument();
  });

  it("says a confirmed photo isn't ready, lists what to place, and offers no generate link", () => {
    renderReview({
      fromLiveApi: true,
      fusion: fusion(),
      targetRackId: 3,
      revisionId: "inv-rev-1",
      readyForGeneration: false,
      modulesToPlace: [
        {
          instance_id: "inst-1",
          module_revision_id: "catalog-cand-1",
          manufacturer: "Sim",
          model: "Oscillator A",
          module_id: 7,
        },
      ],
    });
    const sealed = screen.getByText(/Inventory revision sealed: inv-rev-1/);
    expect(sealed).toHaveTextContent("not ready for generation");
    expect(sealed).toHaveClass("status-warning");
    expect(screen.queryByRole("link", { name: /Generate patches/ })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open this rig" })).toHaveAttribute("href", "/rigs/3");
    expect(screen.getByRole("link", { name: "Place it" })).toHaveAttribute(
      "href",
      "/racks/3/edit?module_id=7",
    );
  });

  it("offers generation only when the rig is ready", () => {
    renderReview({
      fromLiveApi: true,
      fusion: fusion(),
      targetRackId: 3,
      revisionId: "inv-rev-1",
      readyForGeneration: true,
    });
    const sealed = screen.getByText(/Inventory revision sealed: inv-rev-1/);
    expect(sealed).toHaveTextContent("ready for generation");
    expect(sealed).toHaveClass("status-success");
    expect(screen.getByRole("link", { name: "Generate patches on this rig" })).toBeInTheDocument();
    expect(screen.queryByText(/Still to place/)).not.toBeInTheDocument();
  });
});
