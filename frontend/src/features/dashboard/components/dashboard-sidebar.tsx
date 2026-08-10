"use client";

import { useRef } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { LogOut } from "lucide-react";
import { BrandLogo } from "@/components/brand-logo";
import { cn } from "@/lib/utils";
import { useAuth } from "@/hooks/use-auth";
import { useOverflowState } from "@/features/dashboard/hooks/use-overflow-state";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  dashboardNavigationItems,
  isDashboardNavigationItemActive,
} from "@/features/dashboard/navigation";
import {
  formatDashboardUserName,
  getDashboardUserInitials,
} from "@/features/dashboard/utils/user-profile";
import { DashboardNavigationIcon } from "./dashboard-navigation-icon";
import styles from "./dashboard-sidebar.module.css";

export function DashboardSidebar() {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const navigationRef = useRef<HTMLElement>(null);
  const isNavigationOverflowing = useOverflowState(navigationRef);
  const displayName = user ? formatDashboardUserName(user) : "";
  const initials = user ? getDashboardUserInitials(user) : "";

  return (
    <aside aria-label="Dashboard sidebar" className={styles.sidebar}>
      <BrandLogo className={styles.logo} priority sizes="152px" />
      <nav
        aria-label="Dashboard navigation"
        className={styles.navigation}
        data-overflowing={isNavigationOverflowing ? "true" : "false"}
        ref={navigationRef}
      >
        {dashboardNavigationItems.map(({ href, icon, navigationLabel }) => {
          const isActive = isDashboardNavigationItemActive(pathname, href);

          return (
            <Link
              aria-current={isActive ? "page" : undefined}
              className={cn(styles.item, isActive && styles.itemActive)}
              href={href}
              key={href}
            >
              <DashboardNavigationIcon className={styles.icon} icon={icon} />
              <span>{navigationLabel}</span>
            </Link>
          );
        })}
      </nav>
      {user && (
        <div className={styles.footer}>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button className={styles.profileTrigger} type="button">
                <Avatar className={styles.profileAvatar}>
                  <AvatarFallback className={styles.profileAvatarFallback}>
                    {initials}
                  </AvatarFallback>
                </Avatar>
                <span className={styles.profileName}>{displayName}</span>
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent
              align="start"
              className={styles.profileMenu}
              side="top"
            >
              <div className={styles.profileMenuIdentity}>
                <Avatar className={styles.profileAvatar}>
                  <AvatarFallback className={styles.profileAvatarFallback}>
                    {initials}
                  </AvatarFallback>
                </Avatar>
                <span className={styles.profileMenuName}>{displayName}</span>
              </div>
              <DropdownMenuSeparator className={styles.profileMenuSeparator} />
              <DropdownMenuItem
                className={styles.profileMenuLogout}
                onSelect={() => logout()}
              >
                <LogOut aria-hidden="true" className={styles.profileMenuLogoutIcon} />
                <span>Log out</span>
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      )}
    </aside>
  );
}
