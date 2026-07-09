import { useEffect } from "react";
import { useLocation } from "react-router-dom";

/**
 * ScrollToTop - Global scroll restoration component
 * 
 * Forces scroll to top on every route change.
 * Must be mounted inside Router, above Routes.
 * 
 * Handles hash navigation separately - if there's a hash in the URL,
 * it lets the target page handle the scroll positioning.
 */
const ScrollToTop = () => {
  const { pathname, hash } = useLocation();

  useEffect(() => {
    // Only scroll to top if there's no hash (hash scrolling is handled by target pages)
    if (!hash) {
      window.scrollTo({ top: 0, left: 0, behavior: "instant" });
    }
  }, [pathname, hash]);

  return null;
};

export default ScrollToTop;
