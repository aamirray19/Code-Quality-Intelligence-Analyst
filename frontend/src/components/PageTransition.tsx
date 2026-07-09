import { motion } from "framer-motion";
import { useReducedMotion } from "framer-motion";
import { ReactNode } from "react";

interface PageTransitionProps {
  children: ReactNode;
}

const PageTransition = ({ children }: PageTransitionProps) => {
  const shouldReduceMotion = useReducedMotion();

  return (
    <motion.div
      initial={{ opacity: shouldReduceMotion ? 1 : 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: shouldReduceMotion ? 1 : 0 }}
      transition={
        shouldReduceMotion
          ? { duration: 0 }
          : { duration: 0.25, ease: "easeOut" }
      }
      className="w-full"
    >
      {children}
    </motion.div>
  );
};

export default PageTransition;
