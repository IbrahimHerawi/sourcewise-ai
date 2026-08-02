"use client";

import {
  createContext,
  useContext,
  useId,
  useLayoutEffect,
  useState,
  type Dispatch,
  type ReactNode,
  type SetStateAction,
} from "react";
import { usePathname } from "next/navigation";

export type DashboardHeaderConfiguration = {
  actions?: ReactNode;
  contextualLabel?: string;
  title?: string;
};

type RegisteredDashboardHeader = DashboardHeaderConfiguration & {
  pathname: string;
  registrationId: string;
};

const DashboardHeaderStateContext =
  createContext<RegisteredDashboardHeader | null>(null);
const DashboardHeaderRegistrationContext = createContext<
  Dispatch<SetStateAction<RegisteredDashboardHeader | null>>
>(() => undefined);

export function DashboardHeaderProvider({ children }: { children: ReactNode }) {
  const [header, registerHeader] = useState<RegisteredDashboardHeader | null>(
    null,
  );

  return (
    <DashboardHeaderRegistrationContext.Provider value={registerHeader}>
      <DashboardHeaderStateContext.Provider value={header}>
        {children}
      </DashboardHeaderStateContext.Provider>
    </DashboardHeaderRegistrationContext.Provider>
  );
}

/** Register only the route-specific values that cannot live in static metadata. */
export function useDashboardHeader(
  configuration: DashboardHeaderConfiguration,
): void {
  const pathname = usePathname();
  const registrationId = useId();
  const registerHeader = useContext(DashboardHeaderRegistrationContext);

  useLayoutEffect(() => {
    registerHeader({ ...configuration, pathname, registrationId });

    return () => {
      registerHeader((current) =>
        current?.registrationId === registrationId ? null : current
      );
    };
  }, [configuration, pathname, registerHeader, registrationId]);
}

export function useRegisteredDashboardHeader(): RegisteredDashboardHeader | null {
  return useContext(DashboardHeaderStateContext);
}
