/**
 * Navigation Configuration
 * Single source of truth for nav links used by Navbar.
 */

export interface NavLink {
  label: string;
  href: string;
  isRoute?: boolean;
}

/** Primary nav links — empty for now (single-section landing page). */
export const navLinks: NavLink[] = [];
