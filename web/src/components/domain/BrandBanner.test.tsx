import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { buildQueryMock, MOCK_BRAND } from "@/test/mocks";

vi.mock("@/lib/query", () => buildQueryMock());

import { BrandBanner } from "./BrandBanner";

describe("BrandBanner", () => {
  it("renders the active brand name and tagline", () => {
    render(<BrandBanner />);
    expect(screen.getByTestId("brand-banner")).toBeInTheDocument();
    expect(screen.getByText(MOCK_BRAND.name)).toBeInTheDocument();
    expect(screen.getByText(MOCK_BRAND.tagline)).toBeInTheDocument();
  });

  it("renders palette swatches with title attributes", () => {
    render(<BrandBanner />);
    for (const hex of MOCK_BRAND.palette) {
      expect(screen.getByTitle(hex)).toBeInTheDocument();
    }
  });
});
