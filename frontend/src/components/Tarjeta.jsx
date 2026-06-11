export default function Tarjeta({ children, className = "" }) {
  return (
    <article className={`tarjeta ${className}`.trim()}>
      {children}
    </article>
  );
}
