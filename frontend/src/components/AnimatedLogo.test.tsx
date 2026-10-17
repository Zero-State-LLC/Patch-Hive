/**
 * Tests for AnimatedLogo component
 */
import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { AnimatedLogo } from "./AnimatedLogo";

describe("AnimatedLogo", () => {
  describe("Rendering", () => {
    it("renders without crashing", () => {
      const { container } = render(<AnimatedLogo />);
      const svg = container.querySelector("svg");
      expect(svg).toBeInTheDocument();
    });

    it("renders with default size", () => {
      const { container } = render(<AnimatedLogo />);
      const svg = container.querySelector("svg");
      expect(svg).toHaveAttribute("width", "200");
      expect(svg).toHaveAttribute("height", "200");
    });

    it("renders with custom size", () => {
      const { container } = render(<AnimatedLogo size={300} />);
      const svg = container.querySelector("svg");
      expect(svg).toHaveAttribute("width", "300");
      expect(svg).toHaveAttribute("height", "300");
    });

    it("renders with animation enabled by default", () => {
      const { container } = render(<AnimatedLogo />);
      const svg = container.querySelector("svg");
      expect(svg).toHaveClass("patchhive-logo-animated");
    });

    it("renders with animation disabled when animate=false", () => {
      const { container } = render(<AnimatedLogo animate={false} />);
      const svg = container.querySelector("svg");
      expect(svg).toHaveClass("patchhive-logo-static");
    });

    it("renders with animation explicitly enabled", () => {
      const { container } = render(<AnimatedLogo animate={true} />);
      const svg = container.querySelector("svg");
      expect(svg).toHaveClass("patchhive-logo-animated");
    });
  });

  describe("SVG Structure", () => {
    it("renders outer hexagon", () => {
      const { container } = render(<AnimatedLogo />);
      const outerHex = container.querySelector(".hex-outer");
      expect(outerHex).toBeInTheDocument();
      expect(outerHex).toHaveAttribute("fill", "none");
      expect(outerHex).toHaveAttribute("stroke", "#f5a623");
    });

    it("renders inner hexagon", () => {
      const { container } = render(<AnimatedLogo />);
      const innerHex = container.querySelector(".hex-inner");
      expect(innerHex).toBeInTheDocument();
      expect(innerHex).toHaveAttribute("opacity", "0.6");
    });

    it("renders central core with 3 circles", () => {
      const { container } = render(<AnimatedLogo />);
      const coreOuter = container.querySelector(".core-outer");
      const coreMiddle = container.querySelector(".core-middle");
      const coreInner = container.querySelector(".core-inner");

      expect(coreOuter).toBeInTheDocument();
      expect(coreMiddle).toBeInTheDocument();
      expect(coreInner).toBeInTheDocument();
    });

    it("renders CV pathways group", () => {
      const { container } = render(<AnimatedLogo />);
      const pathways = container.querySelector(".cv-pathways");
      expect(pathways).toBeInTheDocument();
    });

    it("renders all 3 CV pathways", () => {
      const { container } = render(<AnimatedLogo />);
      const pathway1 = container.querySelector(".pathway-1");
      const pathway2 = container.querySelector(".pathway-2");
      const pathway3 = container.querySelector(".pathway-3");

      expect(pathway1).toBeInTheDocument();
      expect(pathway2).toBeInTheDocument();
      expect(pathway3).toBeInTheDocument();
    });

    it("renders signal dots", () => {
      const { container } = render(<AnimatedLogo />);
      const dots = container.querySelectorAll(".signal-dot");
      expect(dots.length).toBeGreaterThanOrEqual(3);
    });

    it("renders voltage markers (6 hexagons at vertices)", () => {
      const { container } = render(<AnimatedLogo />);
      const allPolygons = container.querySelectorAll("polygon");
      // Should have outer hex, inner hex, honeycomb pattern, and 6 voltage markers
      expect(allPolygons.length).toBeGreaterThanOrEqual(8);
    });
  });

  describe("SVG Definitions", () => {
    it("has glow filter defined", () => {
      const { container } = render(<AnimatedLogo />);
      const filter = container.querySelector("#glow-animated");
      expect(filter).toBeInTheDocument();
    });

    it("has honeycomb pattern defined", () => {
      const { container } = render(<AnimatedLogo />);
      const pattern = container.querySelector("#honeycomb-animated");
      expect(pattern).toBeInTheDocument();
    });

    it("honeycomb pattern has correct attributes", () => {
      const { container } = render(<AnimatedLogo />);
      const pattern = container.querySelector("#honeycomb-animated");
      expect(pattern).toHaveAttribute("patternUnits", "userSpaceOnUse");
    });
  });

  describe("Props Validation", () => {
    it("handles size prop of 0", () => {
      const { container } = render(<AnimatedLogo size={0} />);
      const svg = container.querySelector("svg");
      expect(svg).toHaveAttribute("width", "0");
    });

    it("handles large size prop", () => {
      const { container } = render(<AnimatedLogo size={1000} />);
      const svg = container.querySelector("svg");
      expect(svg).toHaveAttribute("width", "1000");
    });

    it("handles both size and animate props together", () => {
      const { container } = render(<AnimatedLogo size={150} animate={false} />);
      const svg = container.querySelector("svg");
      expect(svg).toHaveAttribute("width", "150");
      expect(svg).toHaveClass("patchhive-logo-static");
    });
  });

  describe("CSS Classes", () => {
    it("applies animated class when animate is true", () => {
      const { container } = render(<AnimatedLogo animate={true} />);
      const svg = container.querySelector("svg");
      expect(svg).toHaveClass("patchhive-logo-animated");
      expect(svg).not.toHaveClass("patchhive-logo-static");
    });

    it("applies static class when animate is false", () => {
      const { container } = render(<AnimatedLogo animate={false} />);
      const svg = container.querySelector("svg");
      expect(svg).toHaveClass("patchhive-logo-static");
      expect(svg).not.toHaveClass("patchhive-logo-animated");
    });
  });

  describe("Visual Elements", () => {
    it("all pathways have stroke color #f5a623", () => {
      const { container } = render(<AnimatedLogo />);
      const pathways = container.querySelectorAll('[class*="pathway-"]');
      pathways.forEach((pathway) => {
        expect(pathway).toHaveAttribute("stroke", "#f5a623");
      });
    });

    it("all hexagons use brand color #f5a623", () => {
      const { container } = render(<AnimatedLogo />);
      const hexOuter = container.querySelector(".hex-outer");
      const hexInner = container.querySelector(".hex-inner");
      expect(hexOuter).toHaveAttribute("stroke", "#f5a623");
      expect(hexInner).toHaveAttribute("stroke", "#f5a623");
    });

    it("core circles have correct radii", () => {
      const { container } = render(<AnimatedLogo />);
      const coreOuter = container.querySelector(".core-outer");
      const coreMiddle = container.querySelector(".core-middle");
      const coreInner = container.querySelector(".core-inner");

      expect(coreOuter).toHaveAttribute("r", "35");
      expect(coreMiddle).toHaveAttribute("r", "25");
      expect(coreInner).toHaveAttribute("r", "15");
    });

    it("pathways have proper curve commands", () => {
      const { container } = render(<AnimatedLogo />);
      const pathway1 = container.querySelector(".pathway-1");
      const dAttr = pathway1?.getAttribute("d");
      expect(dAttr).toContain("Q"); // Should have quadratic bezier curves
    });
  });

  describe("Accessibility", () => {
    it("SVG has proper viewBox", () => {
      const { container } = render(<AnimatedLogo />);
      const svg = container.querySelector("svg");
      expect(svg).toHaveAttribute("viewBox", "0 0 400 400");
    });

    it("SVG maintains aspect ratio with different sizes", () => {
      const { container: container1 } = render(<AnimatedLogo size={100} />);
      const { container: container2 } = render(<AnimatedLogo size={400} />);

      const svg1 = container1.querySelector("svg");
      const svg2 = container2.querySelector("svg");

      expect(svg1).toHaveAttribute("viewBox", "0 0 400 400");
      expect(svg2).toHaveAttribute("viewBox", "0 0 400 400");
    });
  });
});
