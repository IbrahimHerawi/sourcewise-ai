"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LogOut } from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/hooks/use-auth";
import {
  dashboardNavigationItems,
  isDashboardNavigationItemActive,
  type DashboardNavigationItem,
} from "@/features/dashboard/navigation";
import styles from "./dashboard-sidebar.module.css";

function NavigationIcon({ icon }: Pick<DashboardNavigationItem, "icon">) {
  if (icon === "document") {
    return (
      <svg aria-hidden="true" className={styles.icon} viewBox="52 128 20 20">
        <path
          fill="currentColor"
          d="M56 144H64V142H56V144V144M56 140H64V138H56V140V140M54 148C53.45 148 52.9792 147.804 52.5875 147.413C52.1958 147.021 52 146.55 52 146V130C52 129.45 52.1958 128.979 52.5875 128.587C52.9792 128.196 53.45 128 54 128H62L68 134V146C68 146.55 67.8042 147.021 67.4125 147.413C67.0208 147.804 66.55 148 66 148H54V148M61 135H66L61 130V135V135"
        />
      </svg>
    );
  }

  if (icon === "question") {
    return (
      <svg aria-hidden="true" className={styles.icon} viewBox="52 180 20 20">
        <path
          fill="currentColor"
          d="M64 193C64.2833 193 64.5292 192.896 64.7375 192.688C64.9458 192.479 65.05 192.233 65.05 191.95C65.05 191.667 64.9458 191.421 64.7375 191.212C64.5292 191.004 64.2833 190.9 64 190.9C63.7167 190.9 63.4708 191.004 63.2625 191.212C63.0542 191.421 62.95 191.667 62.95 191.95C62.95 192.233 63.0542 192.479 63.2625 192.688C63.4708 192.896 63.7167 193 64 193V193M63.25 189.8H64.75C64.75 189.317 64.8 188.963 64.9 188.738C65 188.513 65.2333 188.217 65.6 187.85C66.1 187.35 66.4333 186.946 66.6 186.637C66.7667 186.329 66.85 185.967 66.85 185.55C66.85 184.8 66.5875 184.188 66.0625 183.713C65.5375 183.238 64.85 183 64 183C63.3167 183 62.7208 183.192 62.2125 183.575C61.7042 183.958 61.35 184.467 61.15 185.1L62.5 185.65C62.65 185.233 62.8542 184.921 63.1125 184.713C63.3708 184.504 63.6667 184.4 64 184.4C64.4 184.4 64.725 184.513 64.975 184.738C65.225 184.963 65.35 185.267 65.35 185.65C65.35 185.883 65.2833 186.104 65.15 186.312C65.0167 186.521 64.7833 186.783 64.45 187.1C63.9 187.583 63.5625 187.963 63.4375 188.238C63.3125 188.513 63.25 189.033 63.25 189.8V189.8M58 196C57.45 196 56.9792 195.804 56.5875 195.413C56.1958 195.021 56 194.55 56 194V182C56 181.45 56.1958 180.979 56.5875 180.587C56.9792 180.196 57.45 180 58 180H70C70.55 180 71.0208 180.196 71.4125 180.587C71.8042 180.979 72 181.45 72 182V194C72 194.55 71.8042 195.021 71.4125 195.413C71.0208 195.804 70.55 196 70 196H58V196M54 200C53.45 200 52.9792 199.804 52.5875 199.413C52.1958 199.021 52 198.55 52 198V184H54V198V198V198H68V200H54V200"
        />
      </svg>
    );
  }

  return (
    <svg aria-hidden="true" className={styles.icon} viewBox="52 232 20 20">
      <path
        fill="currentColor"
        d="M61 251C58.7 251 56.6958 250.237 54.9875 248.712C53.2792 247.187 52.3 245.283 52.05 243H54.1C54.3333 244.733 55.1042 246.167 56.4125 247.3C57.7208 248.433 59.25 249 61 249C62.95 249 64.6042 248.321 65.9625 246.962C67.3208 245.604 68 243.95 68 242C68 240.05 67.3208 238.396 65.9625 237.037C64.6042 235.679 62.95 235 61 235C59.85 235 58.775 235.267 57.775 235.8C56.775 236.333 55.9333 237.067 55.25 238H58V240H52V234H54V236.35C54.85 235.283 55.8875 234.458 57.1125 233.875C58.3375 233.292 59.6333 233 61 233C62.25 233 63.4208 233.237 64.5125 233.712C65.6042 234.187 66.5542 234.829 67.3625 235.638C68.1708 236.446 68.8125 237.396 69.2875 238.488C69.7625 239.579 70 240.75 70 242C70 243.25 69.7625 244.421 69.2875 245.512C68.8125 246.604 68.1708 247.554 67.3625 248.363C66.5542 249.171 65.6042 249.813 64.5125 250.288C63.4208 250.763 62.25 251 61 251V251M63.8 246.2L60 242.4V237H62V241.6L65.2 244.8L63.8 246.2V246.2"
      />
    </svg>
  );
}

export function DashboardSidebar() {
  const pathname = usePathname();
  const { user, logout } = useAuth();

  return (
    <aside aria-label="Dashboard sidebar" className={styles.sidebar}>
      <span className={styles.logo}>DocQ&amp;A</span>
      <nav aria-label="Dashboard navigation" className={styles.navigation}>
        {dashboardNavigationItems.map(({ href, icon, label }) => {
          const isActive = isDashboardNavigationItemActive(pathname, href);

          return (
            <Link
              aria-current={isActive ? "page" : undefined}
              className={cn(styles.item, isActive && styles.itemActive)}
              href={href}
              key={href}
            >
              <NavigationIcon icon={icon} />
              <span>{label}</span>
            </Link>
          );
        })}
      </nav>
      {user && (
        <div className={styles.footer}>
          <div className={styles.userInfo}>
            <span className={styles.userName}>
              {user.first_name} {user.last_name}
            </span>
            <span className={styles.userEmail}>{user.email}</span>
          </div>
          <button
            aria-label="Log out of SourceWise"
            className={styles.logoutBtn}
            onClick={logout}
            type="button"
          >
            <LogOut className="size-4 shrink-0" />
            <span>Log Out</span>
          </button>
        </div>
      )}
    </aside>
  );
}
