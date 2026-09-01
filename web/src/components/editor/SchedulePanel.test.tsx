import { describe, expect, it, beforeEach, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { SchedulePanel } from "./SchedulePanel";
import { useEditorStore } from "@/hooks/useEditor";
import type { Template, Product } from "@/lib/types";

const mockSchedule = vi.fn();
const mockJobs = vi.fn();

vi.mock("@/hooks/contentFlow", () => ({
  useSchedule: () => ({
    mutate: (input: unknown) => mockSchedule(input),
    isPending: false,
  }),
  useSchedulerJobs: () => ({
    data: mockJobs(),
    isLoading: false,
  }),
}));

describe("SchedulePanel", () => {
  beforeEach(() => {
    mockSchedule.mockClear();
    mockJobs.mockReset();
    mockJobs.mockReturnValue({ jobs: [] });
    useEditorStore.setState((s) => {
      s.template = null;
      s.product = null;
      s.brand = null;
    });
  });

  it("disables Schedule when template/product missing", () => {
    render(<SchedulePanel />);
    expect(screen.getByTestId("schedule-output")).toBeDisabled();
  });

  it("submits a publish_output job to the scheduler", async () => {
    useEditorStore.setState((s) => {
      s.template = { id: 1, name: "T", aspect_ratio: "1:1", canvas: { width: 10, height: 10 }, layers: [] } as unknown as Template;
      s.product = { id: 2, name: "P" } as unknown as Product;
      s.brand = { id: 3, name: "B" } as unknown as import("@/lib/types").Brand;
    });
    render(<SchedulePanel />);
    await userEvent.click(screen.getByTestId("schedule-output"));
    expect(mockSchedule).toHaveBeenCalledOnce();
    const payload = mockSchedule.mock.calls[0][0];
    expect(payload.kind).toBe("publish_output");
    expect(payload.payload).toMatchObject({
      output_id: 0,
      product_id: 2,
      template_id: 1,
      brand_id: 3,
      platform: "instagram",
    });
    expect(payload.run_at).toBeGreaterThan(Date.now() / 1000);
  });

  it("renders queued-job count", () => {
    mockJobs.mockReturnValue({ jobs: [{ id: 1 }, { id: 2 }, { id: 3 }] });
    useEditorStore.setState((s) => {
      s.template = { id: 1, name: "T", aspect_ratio: "1:1", canvas: { width: 10, height: 10 }, layers: [] } as unknown as Template;
      s.product = { id: 1, name: "P" } as unknown as Product;
    });
    render(<SchedulePanel />);
    expect(screen.getByText(/3 queued jobs/)).toBeInTheDocument();
  });
});