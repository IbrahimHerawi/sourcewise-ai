import { createRef, type ReactElement, type ReactNode } from "react";
import {
  render,
  type RenderOptions,
  type RenderResult,
} from "@testing-library/react";
import { DashboardHeader } from "@/features/dashboard/components/dashboard-header";
import { DashboardHeaderProvider } from "@/features/dashboard/components/dashboard-header-context";

function DashboardHeaderTestLayout({ children }: { children: ReactNode }) {
  return (
    <DashboardHeaderProvider>
      <DashboardHeader scrollContainerRef={createRef<HTMLElement>()} />
      {children}
    </DashboardHeaderProvider>
  );
}

export function renderWithDashboardHeader(
  ui: ReactElement,
  options: Omit<RenderOptions, "wrapper"> = {},
): RenderResult {
  return render(ui, {
    wrapper: DashboardHeaderTestLayout,
    ...options,
  });
}
