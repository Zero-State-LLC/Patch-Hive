import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
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

function renderReview(props: { fromLiveApi: boolean; fusion: FusionView }) {
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
});
