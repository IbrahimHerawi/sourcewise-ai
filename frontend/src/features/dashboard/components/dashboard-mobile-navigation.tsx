"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { LogOut, Menu } from "lucide-react";
import { BrandLogo } from "@/components/brand-logo";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useAuth } from "@/hooks/use-auth";
import { cn } from "@/lib/utils";
import {
  dashboardNavigationItems,
  isDashboardNavigationItemActive,
} from "@/features/dashboard/navigation";
import {
  formatDashboardUserName,
  getDashboardUserInitials,
} from "@/features/dashboard/utils/user-profile";
import { DashboardNavigationIcon } from "./dashboard-navigation-icon";
import styles from "./dashboard-mobile-navigation.module.css";

export function DashboardMobileNavigation() {
  const pathname = usePathname();
  const { logout, user } = useAuth();
  const [open, setOpen] = useState(false);
  const displayName = user ? formatDashboardUserName(user) : "";
  const initials = user ? getDashboardUserInitials(user) : "";

  return (
    <header aria-label="Mobile header" className={styles.topBar}>
      <BrandLogo className={styles.brand} priority sizes="136px" />
      <DropdownMenu modal={false} onOpenChange={setOpen} open={open}>
        <DropdownMenuTrigger asChild>
          <button
            aria-expanded={open}
            aria-label="Dashboard navigation"
            className={styles.menuTrigger}
            type="button"
          >
            <Menu aria-hidden="true" />
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent
          align="end"
          aria-label="Dashboard navigation"
          className={styles.menuContent}
          collisionPadding={16}
          side="bottom"
          sideOffset={8}
        >
          {dashboardNavigationItems.map(({ href, icon, navigationLabel }) => {
            const isActive = isDashboardNavigationItemActive(pathname, href);

            return (
              <DropdownMenuItem
                asChild
                className={cn(styles.menuItem, isActive && styles.menuItemActive)}
                key={href}
                onSelect={() => setOpen(false)}
              >
                <Link aria-current={isActive ? "page" : undefined} href={href}>
                  <DashboardNavigationIcon className={styles.menuIcon} icon={icon} />
                  <span>{navigationLabel}</span>
                </Link>
              </DropdownMenuItem>
            );
          })}

          {user ? (
            <>
              <DropdownMenuSeparator className={styles.separator} />
              <DropdownMenuLabel className={styles.profile}>
                <Avatar className={styles.avatar}>
                  <AvatarFallback className={styles.avatarFallback}>
                    {initials}
                  </AvatarFallback>
                </Avatar>
                <span className={styles.profileName}>{displayName}</span>
              </DropdownMenuLabel>
              <DropdownMenuItem
                className={styles.logout}
                onSelect={() => {
                  setOpen(false);
                  void logout();
                }}
              >
                <LogOut aria-hidden="true" className={styles.menuIcon} />
                <span>Log out</span>
              </DropdownMenuItem>
            </>
          ) : null}
        </DropdownMenuContent>
      </DropdownMenu>
    </header>
  );
}
