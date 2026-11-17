import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { ArrowLeft, Compass, Home } from "lucide-react";
import { Button } from "../components/ui";

export default function NotFoundPage() {
  const navigate = useNavigate();
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center text-center">
      <motion.div
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ type: "spring", stiffness: 200, damping: 18 }}
        className="relative"
      >
        <div className="text-gradient select-none text-[7rem] font-bold leading-none tracking-tighter sm:text-[9rem]">404</div>
        <motion.div
          className="absolute -right-4 -top-2 flex h-12 w-12 items-center justify-center rounded-2xl bg-white/80 shadow-xl ring-1 ring-slate-200 dark:bg-white/10 dark:ring-white/10"
          animate={{ rotate: [0, 20, -10, 0] }}
          transition={{ duration: 3, repeat: Infinity }}
        >
          <Compass className="h-6 w-6 text-indigo-500" />
        </motion.div>
      </motion.div>
      <h1 className="mt-4 text-xl font-semibold text-slate-900 dark:text-white">This page wandered off</h1>
      <p className="muted mt-2 max-w-sm text-sm">The page you’re looking for doesn’t exist or may have been moved.</p>
      <div className="mt-6 flex gap-2">
        <Button variant="outline" leftIcon={<ArrowLeft className="h-4 w-4" />} onClick={() => navigate(-1)}>
          Go back
        </Button>
        <Button variant="gradient" leftIcon={<Home className="h-4 w-4" />} onClick={() => navigate("/")}>
          Dashboard
        </Button>
      </div>
    </div>
  );
}
