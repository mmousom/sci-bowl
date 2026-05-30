"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useSession, signOut } from "next-auth/react";

/** Design token for the nav border colour. */
const BORDER_COLOR_LIGHT = "#d9d9e4";
const BORDER_COLOR_DARK = "#2a2a3a";

const STATS_ICON_PATH =
  "M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z";

interface NavItem {
  href: string;
  label: string;
  /** SVG path data for the icon. */
  iconPath: string;
}

/** Nav items always shown in the desktop top bar. */
const DESKTOP_NAV_ITEMS_BASE: NavItem[] = [
  {
    href: "/practice",
    label: "Practice",
    iconPath: "M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5",
  },
  {
    href: "/simulation",
    label: "Simulation",
    iconPath:
      "M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z M21 12a9 9 0 11-18 0 9 9 0 0118 0z",
  },
];

const STATS_NAV_ITEM: NavItem = {
  href: "/stats",
  label: "Stats",
  iconPath: STATS_ICON_PATH,
};

/** Nav items always shown in the mobile bottom bar. */
const MOBILE_NAV_ITEMS_BASE: NavItem[] = [
  {
    href: "/practice",
    label: "Practice",
    iconPath: "M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5",
  },
  {
    href: "/simulation",
    label: "Simulation",
    iconPath:
      "M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z M21 12a9 9 0 11-18 0 9 9 0 0118 0z",
  },
  {
    href: "/profile",
    label: "Profile",
    iconPath:
      "M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z",
  },
];

/** Renders a single SVG icon for the nav bar. */
function NavIcon({ path }: { path: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      className="h-6 w-6"
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
      aria-hidden="true"
    >
      <path strokeLinecap="round" strokeLinejoin="round" d={path} />
    </svg>
  );
}

/**
 * Responsive navigation component.
 * - Mobile (< 768px): fixed bottom bar with icon + label.
 * - Desktop (≥ 768px): sticky top bar with BowlPrep brand logo left, nav links centred.
 * - When authenticated: shows Stats link, user display name, and Sign Out button.
 * - When unauthenticated: hides Stats link and user info.
 */
export default function Nav() {
  const pathname = usePathname();
  const { data: session, status } = useSession();
  const isAuthenticated = status === "authenticated";

  const isDark =
    typeof window !== "undefined" &&
    window.matchMedia("(prefers-color-scheme: dark)").matches;
  const borderColor = isDark ? BORDER_COLOR_DARK : BORDER_COLOR_LIGHT;

  const desktopNavItems = isAuthenticated
    ? [...DESKTOP_NAV_ITEMS_BASE, STATS_NAV_ITEM]
    : DESKTOP_NAV_ITEMS_BASE;

  const mobileNavItems = isAuthenticated
    ? [MOBILE_NAV_ITEMS_BASE[0], STATS_NAV_ITEM, ...MOBILE_NAV_ITEMS_BASE.slice(1)]
    : MOBILE_NAV_ITEMS_BASE;

  return (
    <>
      {/* ── Desktop top bar ── */}
      <header
        className="hidden md:flex items-center sticky top-0 z-50 bg-surface dark:bg-[#0f0f14] px-6 h-14"
        style={{ borderBottom: `1px solid ${borderColor}` }}
      >
        {/* Brand logo */}
        <span className="text-primary font-bold text-lg tracking-tight select-none">
          BowlPrep
        </span>

        {/* Centred nav links */}
        <nav
          className="absolute left-1/2 -translate-x-1/2 flex items-center gap-8"
          aria-label="Main navigation"
        >
          {desktopNavItems.map(({ href, label }) => {
            const isActive = pathname.startsWith(href);
            return (
              <Link
                key={href}
                href={href}
                className={[
                  "text-sm font-medium transition-colors",
                  isActive
                    ? "text-primary border-b-2 border-primary pb-0.5"
                    : "text-gray-500 dark:text-gray-400 hover:text-primary",
                ].join(" ")}
                aria-current={isActive ? "page" : undefined}
              >
                {label}
              </Link>
            );
          })}
        </nav>

        {/* Auth area — right side */}
        {isAuthenticated && (
          <div className="ml-auto flex items-center gap-3">
            <span className="text-sm text-gray-600 dark:text-gray-300">
              {session?.user?.name}
            </span>
            <button
              onClick={() => signOut({ callbackUrl: "/login" })}
              className="rounded-md border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-600 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-primary/30 dark:border-gray-600 dark:text-gray-300 dark:hover:bg-gray-800"
            >
              Sign Out
            </button>
          </div>
        )}
      </header>

      {/* ── Mobile bottom bar ── */}
      <nav
        className="md:hidden fixed bottom-0 inset-x-0 z-50 bg-surface dark:bg-[#0f0f14] flex items-center justify-around h-14"
        style={{ borderTop: `1px solid ${borderColor}` }}
        aria-label="Main navigation"
      >
        {mobileNavItems.map(({ href, label, iconPath }) => {
          const isActive = pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={[
                "flex flex-col items-center gap-0.5 text-xs font-medium transition-colors",
                isActive ? "text-primary" : "text-gray-500 dark:text-gray-400",
              ].join(" ")}
              aria-current={isActive ? "page" : undefined}
            >
              <NavIcon path={iconPath} />
              <span>{label}</span>
            </Link>
          );
        })}
      </nav>
    </>
  );
}
