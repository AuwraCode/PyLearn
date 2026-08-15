const MARK_OPEN = "\x02";
const MARK_CLOSE = "\x03";

/** Renderuje snippet FTS: fragmenty między \x02 i \x03 trafiają do <mark>.
 * Zero dangerouslySetInnerHTML — treść notatek nie jest wykonywana jako HTML. */
export function Highlighted({ text }: { text: string }) {
  const parts = text.split(MARK_OPEN);
  return (
    <>
      {parts.map((part, index) => {
        if (index === 0) return <span key={index}>{part}</span>;
        const closeAt = part.indexOf(MARK_CLOSE);
        if (closeAt === -1) return <span key={index}>{part}</span>;
        return (
          <span key={index}>
            <mark>{part.slice(0, closeAt)}</mark>
            {part.slice(closeAt + 1)}
          </span>
        );
      })}
    </>
  );
}
