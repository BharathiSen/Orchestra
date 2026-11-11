import type { ReactNode } from "react";

import type { Conversation } from "@/lib/api";

/**
 * Conversation list. A slide-over drawer below `lg` so the chat itself is the
 * primary view on a phone; a static grid column at `lg` and above, where
 * `open` is ignored.
 */
export function ConversationSidebar({
  conversations,
  activeConversationId,
  open,
  onClose,
  onNewChat,
  onSelect,
  onDelete,
  children,
}: {
  conversations: Conversation[];
  activeConversationId: number | null;
  open: boolean;
  onClose: () => void;
  onNewChat: () => void;
  onSelect: (id: number) => void;
  onDelete: (id: number) => void;
  /** Rendered under the list (the memory panel). */
  children?: ReactNode;
}) {
  return (
    <>
      {/* Backdrop for the drawer. Only below `lg`, where the aside is fixed. */}
      {open && (
        <button
          type="button"
          aria-label="Close conversations"
          onClick={onClose}
          className="fixed inset-0 z-30 bg-black/60 lg:hidden"
        />
      )}

      <aside
        id="conversation-drawer"
        aria-label="Conversations"
        className={`min-h-0 overflow-y-auto rounded-2xl border border-line bg-surface p-3 transition-transform duration-200 ease-out
          max-lg:fixed max-lg:inset-y-0 max-lg:left-0 max-lg:z-40 max-lg:w-[86%] max-lg:max-w-[330px] max-lg:rounded-none max-lg:shadow-xl
          ${open ? "max-lg:translate-x-0" : "max-lg:-translate-x-full"}
          lg:bg-surface/80`}
      >
        <div className="mb-3 flex items-center justify-between gap-2">
          <h2 className="text-sm font-semibold text-fg">Conversations</h2>
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={onNewChat}
              className="touch-row inline-flex items-center rounded-md bg-fg px-3 text-xs font-medium text-ground"
            >
              New
            </button>
            <button
              type="button"
              onClick={onClose}
              aria-label="Close conversations"
              className="touch-target inline-flex items-center justify-center rounded-md text-fg-subtle hover:bg-raised lg:hidden"
            >
              <span aria-hidden className="text-xl leading-none">×</span>
            </button>
          </div>
        </div>
        <ul className="mb-3 space-y-1 lg:max-h-[40vh] lg:overflow-y-auto">
          {conversations.length === 0 && (
            <li className="rounded-lg border border-dashed border-line-strong px-3 py-6 text-center text-xs text-fg-subtle">
              No conversations yet.
              <br />
              Send a message to start one.
            </li>
          )}
          {conversations.map((c) => (
            <li key={c.id}>
              <div
                className={`flex items-center gap-1 rounded-lg px-2 text-sm ${
                  activeConversationId === c.id
                    ? "bg-accent/10 text-accent"
                    : "hover:bg-raised"
                }`}
              >
                <button
                  type="button"
                  className="touch-row min-w-0 flex-1 truncate text-left"
                  onClick={() => {
                    onSelect(c.id);
                    onClose();
                  }}
                >
                  {c.title}
                </button>
                <button
                  type="button"
                  className="touch-target inline-flex shrink-0 items-center justify-center rounded-md text-red-300 hover:bg-red-500/10"
                  onClick={() => onDelete(c.id)}
                  aria-label={`Delete conversation ${c.title}`}
                >
                  <span aria-hidden className="text-lg leading-none">×</span>
                </button>
              </div>
            </li>
          ))}
        </ul>

        {children}
      </aside>
    </>
  );
}
