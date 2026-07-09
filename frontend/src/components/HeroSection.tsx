import RepoAnalyzer from "./RepoAnalyzer";
import HeroLightRays from "./HeroLightRays";
import { useScrollParallax } from "@/hooks/use-parallax";

const HeroSection = () => {
  const headlineParallax = useScrollParallax(0.08);
  const subheadlineParallax = useScrollParallax(0.05);

  return (
    <section className="relative min-h-screen flex flex-col">
      {/* Light rays background */}
      <HeroLightRays />

      {/* Hero Content */}
      <div className="container mx-auto px-4 md:px-6 pt-28 md:pt-32 pb-12 md:pb-16 relative z-10 flex-1 flex items-center">
        <div className="max-w-4xl mx-auto text-center">
          {/* Badge */}
          <div
            className="inline-flex items-center gap-2 bg-secondary/50 backdrop-blur-md rounded-full px-3 sm:px-4 py-1.5 mb-6 sm:mb-8 opacity-0"
            style={{ animation: "heroFadeIn 0.6s ease-out 0.2s forwards" }}
          >
            <span
              className="w-2 h-2 bg-primary rounded-full animate-pulse flex-shrink-0"
              aria-hidden="true"
            />
            <span className="text-xs sm:text-sm text-foreground">
              Now analyzing codebases
            </span>
          </div>

          {/* Main Headline */}
          <h1
            className="text-3xl sm:text-4xl md:text-5xl lg:text-6xl font-bold leading-tight tracking-tight mb-4 sm:mb-6 xl:text-6xl opacity-0"
            style={{
              animation: "heroFadeIn 0.7s ease-out 0.3s forwards",
              transform: `translateY(${headlineParallax}px)`,
            }}
          >
            Analyze Code. Eliminate Risk.
            <br className="hidden sm:block" />
            <span className="sm:hidden"> </span>
            <span
              className="font-lora inline-block bg-gradient-to-r from-primary via-amber-400 to-yellow-300 bg-clip-text text-transparent"
              style={{ animation: "subtleGlow 3s ease-in-out infinite" }}
            >
              Code Quality Intelligence Agents
            </span>{" "}
          </h1>

          {/* Subheadline */}
          <p
            className="text-base sm:text-lg md:text-xl text-muted-foreground max-w-xl sm:max-w-2xl mx-auto mb-8 sm:mb-12 opacity-0 px-2"
            style={{
              animation: "heroFadeIn 0.6s ease-out 0.45s forwards",
              transform: `translateY(${subheadlineParallax}px)`,
            }}
          >
            Point it at any repository — get a deep report on bugs, smells, security,
            and complexity in seconds.
          </p>

          {/* Repo Analyzer */}
          <div
            className="opacity-0"
            style={{ animation: "heroFadeIn 0.6s ease-out 0.55s forwards" }}
          >
            <RepoAnalyzer />
          </div>
        </div>
      </div>

      <style>{`
        @keyframes subtleGlow {
          0%, 100% {
            filter: brightness(1) drop-shadow(0 0 0px hsl(var(--primary) / 0));
          }
          50% {
            filter: brightness(1.1) drop-shadow(0 0 16px hsl(45 90% 55% / 0.45));
          }
        }
        @keyframes heroFadeIn {
          from { opacity: 0; transform: translateY(20px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </section>
  );
};

export default HeroSection;
