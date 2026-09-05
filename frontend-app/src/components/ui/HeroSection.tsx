import { motion, type Variants } from 'framer-motion';
import PipoGradient from './PipoGradient';
import FargeGradient from './FargeGradient';

const containerVariants: Variants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { staggerChildren: 0.2, delayChildren: 0.3 } },
};

const itemVariants: Variants = {
  hidden: { y: 20, opacity: 0 },
  visible: { y: 0, opacity: 1, transition: { duration: 0.5, ease: 'easeInOut' } },
};

export default function HeroSection({
  title, subtitle, primaryButtonText, onPrimaryClick,
}: {
  title: string;
  subtitle: string;
  primaryButtonText: string;
  onPrimaryClick?: () => void;
}) {
  return (
    <section className="relative flex min-h-[700px] w-full items-center justify-center overflow-hidden py-24 lg:py-32">
      <PipoGradient className="dark:hidden" />
      <FargeGradient className="hidden dark:block" />

      <motion.div
        className="z-10 flex max-w-4xl flex-col items-center justify-center text-center px-6"
        variants={containerVariants}
        initial="hidden"
        animate="visible"
      >
        <motion.p className="mb-5 text-[11px] font-semibold uppercase tracking-[0.2em] text-gray-500 dark:text-gray-300" variants={itemVariants}>
          Local AI · No cloud processing
        </motion.p>

        <motion.h1
          className="text-[2.75rem] font-bold leading-[1.08] tracking-tight text-gray-900 dark:text-white sm:text-5xl lg:text-[3.5rem]"
          variants={itemVariants}
        >
          {title}
        </motion.h1>

        <motion.p className="mx-auto mt-7 max-w-xl text-[17px] leading-relaxed text-gray-600 dark:text-gray-200" variants={itemVariants}>
          {subtitle}
        </motion.p>

        <motion.div className="mt-9 flex justify-center" variants={itemVariants}>
          <button type="button" className="pearl-button" onClick={onPrimaryClick}>
            <div className="wrap">
              <p><span>✧</span><span>✦</span>{primaryButtonText}</p>
            </div>
          </button>
        </motion.div>

        <motion.p className="mt-5 text-xs text-gray-500 dark:text-gray-400" variants={itemVariants}>
          10 free clips to start. No credit card.
        </motion.p>
      </motion.div>
    </section>
  );
}
