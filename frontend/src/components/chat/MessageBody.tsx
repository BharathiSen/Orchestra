import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

/**
 * Assistant output is Markdown — models emit `**bold**`, lists, tables, and
 * fenced code. Rendering it into `whitespace-pre-wrap` showed the raw syntax.
 *
 * User messages are deliberately NOT parsed as Markdown: what someone typed
 * should appear exactly as typed, so they keep plain text with preserved
 * whitespace.
 */
export function MessageBody({ role, content }: { role: string; content: string }) {
  if (role !== "assistant") {
    return <span className="whitespace-pre-wrap">{content}</span>;
  }

  return (
    <div className="markdown-body text-sm leading-relaxed">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
          strong: ({ children }) => (
            <strong className="font-semibold text-fg">{children}</strong>
          ),
          ul: ({ children }) => (
            <ul className="mb-2 ml-5 list-disc space-y-1 last:mb-0">{children}</ul>
          ),
          ol: ({ children }) => (
            <ol className="mb-2 ml-5 list-decimal space-y-1 last:mb-0">{children}</ol>
          ),
          h1: ({ children }) => (
            <h1 className="mt-3 mb-2 font-display text-base font-semibold first:mt-0">
              {children}
            </h1>
          ),
          h2: ({ children }) => (
            <h2 className="mt-3 mb-2 font-display text-base font-semibold first:mt-0">
              {children}
            </h2>
          ),
          h3: ({ children }) => (
            <h3 className="mt-3 mb-1 font-display text-sm font-semibold first:mt-0">
              {children}
            </h3>
          ),
          a: ({ children, href }) => (
            <a
              href={href}
              target="_blank"
              rel="noreferrer noopener"
              className="text-accent underline underline-offset-2"
            >
              {children}
            </a>
          ),
          blockquote: ({ children }) => (
            <blockquote className="my-2 border-l-2 border-line-strong pl-3 text-fg-muted">
              {children}
            </blockquote>
          ),
          hr: () => <hr className="my-3 border-line-strong" />,
          // Wide tables and long code lines scroll inside the bubble rather
          // than stretching it past the column.
          table: ({ children }) => (
            <div className="my-2 overflow-x-auto">
              <table className="w-full border-collapse text-xs">{children}</table>
            </div>
          ),
          th: ({ children }) => (
            <th className="border border-line-strong bg-line/60 px-2 py-1 text-left font-semibold">
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td className="border border-line-strong px-2 py-1 align-top">{children}</td>
          ),
          pre: ({ children }) => (
            <pre className="my-2 overflow-x-auto rounded-lg bg-ground p-3 text-xs text-fg">
              {children}
            </pre>
          ),
          code: ({ className, children, ...props }) => {
            // react-markdown renders inline code without a language class and
            // fenced blocks with one; only the inline case needs a chip style.
            const isBlock = Boolean(className);
            if (isBlock) {
              return (
                <code className={`${className ?? ""} font-mono`} {...props}>
                  {children}
                </code>
              );
            }
            return (
              <code className="rounded bg-line px-1 py-0.5 font-mono text-[0.85em] text-fg">
                {children}
              </code>
            );
          },
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
