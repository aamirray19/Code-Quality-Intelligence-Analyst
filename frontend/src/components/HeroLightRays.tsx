import { useScrollParallax } from '@/hooks/use-parallax';

const HeroLightRays = () => {
  const scrollOffset = useScrollParallax(0.15);
  const gridOffset = useScrollParallax(0.05);

  return (
    <div 
      className="absolute inset-0 overflow-hidden pointer-events-none"
      style={{ zIndex: 0 }}
    >
      {/* Base dark layer */}
      <div 
        className="absolute inset-0"
        style={{
          background: `hsl(var(--background))`,
        }}
      />

      {/* Animated ray container with parallax */}
      <div 
        className="absolute inset-0"
        style={{
          transform: `translateY(${scrollOffset * 0.5}px)`,
          willChange: 'transform',
        }}
      >
        {/* Ray 1 - Center left */}
        <div 
          className="absolute top-0 left-1/2 origin-top animate-ray-sway-1"
          style={{
            width: '300px',
            height: '120%',
            transform: `translateX(-50%) rotate(-25deg) translateY(${scrollOffset * 0.3}px)`,
            background: `linear-gradient(
              to bottom,
              hsl(24 95% 50% / 0.6) 0%,
              hsl(24 95% 45% / 0.4) 30%,
              hsl(24 95% 40% / 0.15) 60%,
              transparent 100%
            )`,
            filter: 'blur(40px)',
          }}
        />

        {/* Ray 2 - Center */}
        <div 
          className="absolute top-0 left-1/2 origin-top animate-ray-sway-2"
          style={{
            width: '280px',
            height: '120%',
            transform: `translateX(-50%) rotate(-8deg) translateY(${scrollOffset * 0.2}px)`,
            background: `linear-gradient(
              to bottom,
              hsl(24 95% 55% / 0.7) 0%,
              hsl(24 95% 50% / 0.45) 25%,
              hsl(24 95% 45% / 0.18) 55%,
              transparent 100%
            )`,
            filter: 'blur(35px)',
          }}
        />

        {/* Ray 3 - Center right */}
        <div 
          className="absolute top-0 left-1/2 origin-top animate-ray-sway-3"
          style={{
            width: '260px',
            height: '120%',
            transform: `translateX(-50%) rotate(12deg) translateY(${scrollOffset * 0.35}px)`,
            background: `linear-gradient(
              to bottom,
              hsl(24 95% 52% / 0.65) 0%,
              hsl(24 95% 48% / 0.4) 28%,
              hsl(24 95% 42% / 0.15) 58%,
              transparent 100%
            )`,
            filter: 'blur(38px)',
          }}
        />

        {/* Ray 4 - Far left */}
        <div 
          className="absolute top-0 left-1/2 origin-top animate-ray-sway-4"
          style={{
            width: '220px',
            height: '110%',
            transform: `translateX(-50%) rotate(-42deg) translateY(${scrollOffset * 0.4}px)`,
            background: `linear-gradient(
              to bottom,
              hsl(24 95% 48% / 0.55) 0%,
              hsl(24 95% 42% / 0.3) 35%,
              hsl(24 95% 38% / 0.1) 65%,
              transparent 100%
            )`,
            filter: 'blur(45px)',
          }}
        />

        {/* Ray 5 - Far right */}
        <div 
          className="absolute top-0 left-1/2 origin-top animate-ray-sway-5"
          style={{
            width: '240px',
            height: '110%',
            transform: `translateX(-50%) rotate(35deg) translateY(${scrollOffset * 0.25}px)`,
            background: `linear-gradient(
              to bottom,
              hsl(24 95% 50% / 0.58) 0%,
              hsl(24 95% 44% / 0.32) 32%,
              hsl(24 95% 40% / 0.12) 62%,
              transparent 100%
            )`,
            filter: 'blur(42px)',
          }}
        />

        {/* Ray 6 - Extra left */}
        <div 
          className="absolute top-0 left-1/2 origin-top animate-ray-sway-6"
          style={{
            width: '180px',
            height: '100%',
            transform: `translateX(-50%) rotate(-58deg) translateY(${scrollOffset * 0.45}px)`,
            background: `linear-gradient(
              to bottom,
              hsl(24 95% 45% / 0.45) 0%,
              hsl(24 95% 40% / 0.22) 40%,
              transparent 80%
            )`,
            filter: 'blur(50px)',
          }}
        />
      </div>

      {/* Top glow source with parallax */}
      <div 
        className="absolute -top-20 left-1/2 -translate-x-1/2 w-[140%] h-[350px] animate-glow-breathe"
        style={{
          transform: `translateX(-50%) translateY(${scrollOffset * 0.1}px)`,
          background: `radial-gradient(
            ellipse 70% 100% at 50% 0%,
            hsl(24 95% 55% / 0.7) 0%,
            hsl(24 95% 50% / 0.4) 30%,
            hsl(24 95% 45% / 0.15) 60%,
            transparent 100%
          )`,
          willChange: 'transform',
        }}
      />

      {/* Grid texture overlay with subtle parallax */}
      <div 
        className="absolute inset-0 opacity-[0.12]"
        style={{
          backgroundImage: `
            linear-gradient(hsl(24 40% 60% / 0.4) 1px, transparent 1px),
            linear-gradient(90deg, hsl(24 40% 60% / 0.4) 1px, transparent 1px)
          `,
          backgroundSize: '50px 50px',
          backgroundPosition: `0 ${gridOffset}px`,
          willChange: 'background-position',
        }}
      />

      {/* Bottom fade to background */}
      <div 
        className="absolute bottom-0 left-0 right-0 h-[40%]"
        style={{
          background: `linear-gradient(to top, 
            hsl(var(--background)) 0%, 
            hsl(var(--background) / 0.8) 40%,
            transparent 100%
          )`,
        }}
      />
    </div>
  );
};

export default HeroLightRays;
