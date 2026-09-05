import { motion } from 'framer-motion';
import { CheckCircle } from 'lucide-react';
import logoUrl from '../../assets/logo.png';
import { useAuthStore } from '../../stores/auth';
import PipoGradient from '../../components/ui/PipoGradient';
import FargeGradient from '../../components/ui/FargeGradient';

export default function Done() {
  const { user } = useAuthStore();

  return (
    <div className="relative min-h-screen flex items-center justify-center overflow-hidden bg-white dark:bg-black">
      <PipoGradient className="dark:hidden opacity-40" />
      <FargeGradient className="hidden dark:block opacity-40" />

      <motion.div
        initial={{ opacity: 0, y: 20, scale: 0.95 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] as const }}
        className="relative z-10 max-w-md w-full mx-6 p-10 bg-white/20 dark:bg-black/30 backdrop-blur-xl rounded-2xl border border-white/30 dark:border-white/15 shadow-2xl text-center"
      >
        <div className="mx-auto mb-5 grid place-items-center w-16 h-16 rounded-full bg-green-500/15 dark:bg-green-400/10 border border-green-500/30">
          <CheckCircle size={32} className="text-green-600 dark:text-green-400" />
        </div>

        <h1 className="text-2xl font-bold tracking-tight text-gray-900 dark:text-white">
          You're all set{user?.display_name ? `, ${user.display_name}` : ''}.
        </h1>

        <p className="mt-3 text-[15px] leading-relaxed text-gray-600 dark:text-gray-300">
          Your CLPZ account is ready. You can close this tab and open the CLPZ desktop app to start forging clips.
        </p>

        <div className="mt-6 flex flex-col items-center gap-3 text-gray-400 dark:text-gray-500">
          <img src={logoUrl} alt="CLPZ" className="h-6 w-auto opacity-70" />
          <span className="text-xs">CLPZ desktop app is waiting for you</span>
        </div>
      </motion.div>
    </div>
  );
}
