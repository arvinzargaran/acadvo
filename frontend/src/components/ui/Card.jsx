export default function Card({ children, className = '', gradient = false, hover = false }) {
  return (
    <div
      className={`bg-dark-800 border border-dark-600 rounded-xl p-6 relative overflow-hidden ${
        hover ? 'hover:-translate-y-0.5 hover:shadow-md hover:border-primary-500/40 transition-all duration-300' : ''
      } ${className}`}
    >
      {gradient && (
        <div className="absolute top-0 left-0 right-0 h-0.5 bg-primary-500" />
      )}
      {children}
    </div>
  );
}
