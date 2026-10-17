/**
 * Tests for LoadingSpinner component
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { LoadingSpinner } from "./LoadingSpinner";

describe("LoadingSpinner", () => {
  describe("Rendering", () => {
    it("renders without crashing", () => {
      render(<LoadingSpinner />);
      const container = screen.getByRole("img", { hidden: true });
      expect(container).toBeInTheDocument();
    });

    it("renders with default size", () => {
      const { container } = render(<LoadingSpinner />);
      const svg = container.querySelector("svg");
      expect(svg).toHaveAttribute("width", "80");
      expect(svg).toHaveAttribute("height", "80");
    });

    it("renders with custom size", () => {
      const { container } = render(<LoadingSpinner size={120} />);
      const svg = container.querySelector("svg");
      expect(svg).toHaveAttribute("width", "120");
      expect(svg).toHaveAttribute("height", "120");
    });

    it("renders message when provided", () => {
      render(<LoadingSpinner message="Loading modules..." />);
      expect(screen.getByText("Loading modules...")).toBeInTheDocument();
    });

    it("does not render message when not provided", () => {
      const { container } = render(<LoadingSpinner />);
      const message = container.querySelector(".loading-message");
      expect(message).not.toBeInTheDocument();
    });
  });

  describe("SVG Structure", () => {
    it("renders hexagon frame", () => {
      const { container } = render(<LoadingSpinner />);
      const hexFrame = container.querySelector(".spinner-hex");
      expect(hexFrame).toBeInTheDocument();
      expect(hexFrame).toHaveAttribute("fill", "none");
      expect(hexFrame).toHaveAttribute("stroke", "currentColor");
    });

    it("renders inner hexagon", () => {
      const { container } = render(<LoadingSpinner />);
      const innerHex = container.querySelector(".spinner-hex-inner");
      expect(innerHex).toBeInTheDocument();
      expect(innerHex).toHaveAttribute("opacity", "0.6");
    });

    it("renders central core circles", () => {
      const { container } = render(<LoadingSpinner />);
      const coreOuter = container.querySelector(".spinner-core");
      const coreInner = container.querySelector(".spinner-core-inner");
      expect(coreOuter).toBeInTheDocument();
      expect(coreInner).toBeInTheDocument();
    });

    it("renders all 6 orbiting signal dots", () => {
      const { container } = render(<LoadingSpinner />);
      const dots = container.querySelectorAll(".spinner-dot");
      expect(dots).toHaveLength(6);
    });

    it("does not use glow blur filters", () => {
      const { container } = render(<LoadingSpinner />);
      expect(container.querySelector("#spinner-glow")).toBeNull();
      expect(container.querySelector("feGaussianBlur")).toBeNull();
    });
  });

  describe("Props Validation", () => {
    it("handles size prop of 0", () => {
      const { container } = render(<LoadingSpinner size={0} />);
      const svg = container.querySelector("svg");
      expect(svg).toHaveAttribute("width", "0");
    });

    it("handles large size prop", () => {
      const { container } = render(<LoadingSpinner size={500} />);
      const svg = container.querySelector("svg");
      expect(svg).toHaveAttribute("width", "500");
    });

    it("handles empty string message", () => {
      const { container } = render(<LoadingSpinner message="" />);
      const message = container.querySelector(".loading-message");
      expect(message).not.toBeInTheDocument();
    });

    it("handles long message text", () => {
      const longMessage = "Loading a very long message that should still render correctly";
      render(<LoadingSpinner message={longMessage} />);
      expect(screen.getByText(longMessage)).toBeInTheDocument();
    });
  });

  describe("CSS Classes", () => {
    it("has correct container class", () => {
      const { container } = render(<LoadingSpinner />);
      const spinnerContainer = container.firstChild;
      expect(spinnerContainer).toHaveClass("loading-spinner-container");
    });

    it("has correct spinner class on SVG", () => {
      const { container } = render(<LoadingSpinner />);
      const svg = container.querySelector("svg");
      expect(svg).toHaveClass("loading-spinner");
    });

    it("has correct message class", () => {
      render(<LoadingSpinner message="Test" />);
      const message = screen.getByText("Test");
      expect(message).toHaveClass("loading-message");
    });
  });

  describe("Accessibility", () => {
    it("SVG has proper viewBox for scaling", () => {
      const { container } = render(<LoadingSpinner />);
      const svg = container.querySelector("svg");
      expect(svg).toHaveAttribute("viewBox", "0 0 100 100");
    });

    it("message is rendered as paragraph for screen readers", () => {
      render(<LoadingSpinner message="Loading content" />);
      const message = screen.getByText("Loading content");
      expect(message.tagName).toBe("P");
    });
  });
});
