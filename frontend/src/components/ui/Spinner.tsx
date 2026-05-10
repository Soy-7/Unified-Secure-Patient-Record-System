

const sizes = { sm: 'w-5 h-5 border-2', md: 'w-8 h-8 border-3', lg: 'w-12 h-12 border-4' };

export function Spinner({ size = 'md' }: { size?: 'sm' | 'md' | 'lg' }) {
  return (
    <div
      className={`${sizes[size]} rounded-full border-blue-100 border-t-blue-600 animate-spin`}
      style={{ borderTopColor: '#2563eb' }}
    />
  );
}

export function PageSpinner() {
  return (
    <div className="flex items-center justify-center h-48">
      <Spinner size="lg" />
    </div>
  );
}

export function InlineSpinner() {
  return <Spinner size="sm" />;
}
