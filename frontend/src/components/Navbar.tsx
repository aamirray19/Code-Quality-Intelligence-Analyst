import { useState, useEffect } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { navLinks } from "@/config/navigation";
import { Menu, X } from "lucide-react";



const Navbar = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [isScrolled, setIsScrolled] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [activeSection, setActiveSection] = useState("");
  useEffect(() => {
    let scrollTimeout: ReturnType<typeof setTimeout> | null = null;
    const handleScroll = () => {
      setIsScrolled(window.scrollY > 20);

      // Debounce active section detection to prevent jitter
      if (scrollTimeout) clearTimeout(scrollTimeout);
      scrollTimeout = setTimeout(() => {
        const sections = ["curriculum", "reviews", "pricing", "why-us", "faqs"];
        const viewportHeight = window.innerHeight;
        const scrollPosition = window.scrollY;

        // Use 40% viewport threshold for hysteresis
        const threshold = viewportHeight * 0.4;
        let newActiveSection = "";
        for (const section of sections) {
          const element = document.getElementById(section);
          if (element) {
            const rect = element.getBoundingClientRect();
            const elementTop = rect.top;
            const elementBottom = rect.bottom;

            // Section is active when it's clearly in view (40% into viewport)
            if (elementTop <= threshold && elementBottom > threshold * 0.5) {
              newActiveSection = section;
              break;
            }
          }
        }

        // Clear active if at top of page
        if (scrollPosition < 100) {
          newActiveSection = "";
        }
        setActiveSection(newActiveSection);
      }, 50); // Small debounce for smoothness
    };
    window.addEventListener("scroll", handleScroll, {
      passive: true
    });
    return () => {
      window.removeEventListener("scroll", handleScroll);
      if (scrollTimeout) clearTimeout(scrollTimeout);
    };
  }, []);
  const handleSmoothScroll = (e: React.MouseEvent<HTMLAnchorElement>, href: string) => {
    e.preventDefault();
    const targetId = href.replace("#", "");
    
    // If not on homepage, navigate there first with the hash
    if (location.pathname !== "/") {
      navigate("/" + href);
      setIsMobileMenuOpen(false);
      return;
    }
    
    const element = document.getElementById(targetId);
    if (element) {
      // Use getBoundingClientRect for accurate position with nested wrappers
      const rect = element.getBoundingClientRect();
      const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
      const targetPosition = rect.top + scrollTop - 80; // 80px offset for fixed header
      
      window.scrollTo({
        top: targetPosition,
        behavior: "smooth"
      });
    }
    setIsMobileMenuOpen(false);
  };
  return <nav className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${isScrolled ? "bg-background/95 backdrop-blur-md" : "bg-transparent"}`}>
      <div className="container mx-auto px-4 md:px-6 border-0 border-none">
        <div className="flex items-center justify-between h-16 md:h-20 max-w-6xl mx-auto border-0">
          {/* Desktop Navigation */}
          <div className="hidden lg:flex items-center space-x-8">
            {navLinks.map(link => {
              const active = activeSection === link.href.replace("#", "");
              
              return (
                <a 
                  key={link.label} 
                  href={link.href} 
                  onClick={e => handleSmoothScroll(e, link.href)} 
                  className="relative text-sm font-medium" 
                  style={{
                    color: active ? 'hsl(var(--primary))' : 'hsl(var(--foreground))',
                    opacity: active ? 1 : 0.85,
                    transition: 'color 350ms cubic-bezier(0.4, 0, 0.2, 1), opacity 350ms cubic-bezier(0.4, 0, 0.2, 1)'
                  }} 
                  onMouseEnter={e => {
                    if (!active) e.currentTarget.style.opacity = '1';
                  }} 
                  onMouseLeave={e => {
                    if (!active) e.currentTarget.style.opacity = '0.85';
                  }}
                >
                  {link.label}
                  <span 
                    className="absolute -bottom-1 left-0 h-0.5 bg-primary rounded-full" 
                    style={{
                      width: active ? '100%' : '0%',
                      opacity: active ? 1 : 0,
                      transition: 'width 350ms cubic-bezier(0.4, 0, 0.2, 1), opacity 300ms cubic-bezier(0.4, 0, 0.2, 1)'
                    }} 
                  />
                </a>
              );
            })}
          </div>

          {/* Mobile Menu Button (hidden when no nav links) */}
          {navLinks.length > 0 && (
            <div className="flex items-center space-x-4">
              <button
                className="lg:hidden p-2 text-foreground touch-manipulation active:bg-secondary/30 rounded-lg transition-colors"
                onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
                aria-label={isMobileMenuOpen ? "Close menu" : "Open menu"}
                aria-expanded={isMobileMenuOpen}
                aria-controls="mobile-menu"
              >
                {isMobileMenuOpen ? <X size={24} /> : <Menu size={24} />}
              </button>
            </div>
          )}
        </div>

        {/* Mobile Menu */}
        <div 
          className={`lg:hidden bg-background border-t border-border overflow-hidden transition-all duration-300 ease-out ${
            isMobileMenuOpen ? 'max-h-96 opacity-100 py-4' : 'max-h-0 opacity-0 py-0'
          }`}
          aria-hidden={!isMobileMenuOpen}
        >
          <nav className="flex flex-col space-y-1" role="navigation" aria-label="Mobile navigation">
            {navLinks.map(link => {
              const active = activeSection === link.href.replace("#", "");
              
              return (
                <a 
                  key={link.label} 
                  href={link.href} 
                  onClick={e => handleSmoothScroll(e, link.href)} 
                  className="text-sm font-medium px-4 py-3 active:bg-secondary/30 transition-colors touch-manipulation"
                  style={{
                    color: active ? 'hsl(var(--primary))' : 'hsl(var(--muted-foreground))',
                    transition: 'color 350ms cubic-bezier(0.4, 0, 0.2, 1), background-color 150ms ease-out'
                  }}
                  tabIndex={isMobileMenuOpen ? 0 : -1}
                >
                  {link.label}
                </a>
              );
            })}
          </nav>
        </div>
      </div>
    </nav>;
};
export default Navbar;