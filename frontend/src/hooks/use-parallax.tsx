import { useEffect, useState, useRef, RefObject } from 'react';

interface ParallaxOptions {
  speed?: number; // Multiplier for scroll effect (0.1 = slow, 1 = match scroll)
  direction?: 'up' | 'down';
  clamp?: boolean; // Limit maximum displacement
  maxDisplacement?: number;
}

export function useParallax<T extends HTMLElement = HTMLDivElement>(
  options: ParallaxOptions = {}
): { ref: RefObject<T>; offset: number } {
  const { speed = 0.3, direction = 'up', clamp = true, maxDisplacement = 150 } = options;
  const ref = useRef<T>(null);
  const [offset, setOffset] = useState(0);

  useEffect(() => {
    const handleScroll = () => {
      if (!ref.current) return;
      
      const rect = ref.current.getBoundingClientRect();
      const windowHeight = window.innerHeight;
      
      // Calculate how far the element is from center of viewport
      const elementCenter = rect.top + rect.height / 2;
      const viewportCenter = windowHeight / 2;
      const distanceFromCenter = elementCenter - viewportCenter;
      
      // Apply parallax based on distance from center
      let parallaxOffset = distanceFromCenter * speed * (direction === 'up' ? 1 : -1);
      
      // Clamp the offset if needed
      if (clamp) {
        parallaxOffset = Math.max(-maxDisplacement, Math.min(maxDisplacement, parallaxOffset));
      }
      
      setOffset(parallaxOffset);
    };

    window.addEventListener('scroll', handleScroll, { passive: true });
    handleScroll(); // Initial calculation

    return () => window.removeEventListener('scroll', handleScroll);
  }, [speed, direction, clamp, maxDisplacement]);

  return { ref, offset };
}

// Simpler hook for global scroll-based parallax (doesn't need ref)
export function useScrollParallax(speed: number = 0.5): number {
  const [scrollY, setScrollY] = useState(0);

  useEffect(() => {
    const handleScroll = () => {
      setScrollY(window.scrollY * speed);
    };

    window.addEventListener('scroll', handleScroll, { passive: true });
    handleScroll();

    return () => window.removeEventListener('scroll', handleScroll);
  }, [speed]);

  return scrollY;
}
