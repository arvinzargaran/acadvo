export default function Card({ children, className = '', gradient = false, hover = false }) {
  return (
    <div
      className={`card-rich shadow-editorial ring-1 ring-black/5 dark:ring-white/10 rounded-2xl p-6 relative overflow-hidden ${
        hover
          ? 'transition-all duration-300 ease-out hover:-translate-y-1 hover:shadow-[0_1px_2px_rgb(36_30_21_/_0.06),0_10px_24px_rgb(36_30_21_/_0.1),0_36px_72px_-18px_rgb(36_30_21_/_0.28)]'
          : ''
      } ${className}`}
    >
      {gradient && (
        <div className="absolute top-0 left-0 right-0 h-0.5 bg-primary-500 z-10" />
      )}
      {children}
    </div>
  );
}
