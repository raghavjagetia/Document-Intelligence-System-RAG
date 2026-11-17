import { useCallback, useEffect, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { AnimatePresence, motion } from "framer-motion";
import { cn } from "../../lib/utils";

interface Pos {
  /** distance from the viewport top (placement "bottom") or bottom (placement "top") */
  offset: number;
  left: number;
  placement: "top" | "bottom";
}

/**
 * Hover/focus popover rendered in a portal and positioned against the trigger.
 * Used both for small text tooltips and rich content popovers (citations).
 */
export function Popover({
  content,
  children,
  className,
  width = 320,
  openDelay = 120,
  interactive = true,
}: {
  content: ReactNode;
  children: ReactNode;
  className?: string;
  width?: number;
  openDelay?: number;
  interactive?: boolean;
}) {
  const trigger = useRef<HTMLSpanElement>(null);
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState<Pos | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout>>();

  const place = useCallback(() => {
    const el = trigger.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    const vw = window.innerWidth;
    const w = Math.min(width, vw - 16);
    let left = r.left + r.width / 2 - w / 2;
    left = Math.max(8, Math.min(left, vw - w - 8));
    const below = r.top < 220;
    // anchor the popover's own edge to the trigger, so its box never overlaps the trigger
    // (an overlapping box steals the hover and makes the tooltip flicker open/closed)
    setPos({
      offset: below ? r.bottom + 8 : window.innerHeight - r.top + 8,
      left,
      placement: below ? "bottom" : "top",
    });
  }, [width]);

  const show = () => {
    clearTimeout(timer.current);
    timer.current = setTimeout(() => {
      place();
      setOpen(true);
    }, openDelay);
  };
  const hide = () => {
    clearTimeout(timer.current);
    timer.current = setTimeout(() => setOpen(false), interactive ? 120 : 0);
  };

  useLayoutEffect(() => {
    if (open) place();
  }, [open, place]);
  useEffect(() => {
    if (!open) return;
    const onScroll = () => setOpen(false);
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    window.addEventListener("scroll", onScroll, true);
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("scroll", onScroll, true);
      window.removeEventListener("keydown", onKey);
    };
  }, [open]);
  useEffect(() => () => clearTimeout(timer.current), []);

  return (
    <>
      <span
        ref={trigger}
        onMouseEnter={show}
        onMouseLeave={hide}
        onFocus={show}
        onBlur={hide}
        className="inline-flex"
      >
        {children}
      </span>
      {createPortal(
        <AnimatePresence>
          {open && pos && (
            <motion.div
              role="tooltip"
              onMouseEnter={() => interactive && clearTimeout(timer.current)}
              onMouseLeave={hide}
              initial={{ opacity: 0, y: pos.placement === "top" ? 4 : -4, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, scale: 0.98 }}
              transition={{ duration: 0.14 }}
              style={{
                position: "fixed",
                ...(pos.placement === "top" ? { bottom: pos.offset } : { top: pos.offset }),
                left: pos.left,
                width: Math.min(width, window.innerWidth - 16),
                // plain tooltips are display-only: they must never capture the pointer
                pointerEvents: interactive ? "auto" : "none",
              }}
              className={cn("z-[90] flex", !interactive && "justify-center")}
            >
              <div
                className={cn(
                  "glass-strong rounded-xl p-3 text-xs text-slate-700 dark:text-slate-200",
                  !interactive && "w-max max-w-full",
                  className,
                )}
              >
                {content}
              </div>
            </motion.div>
          )}
        </AnimatePresence>,
        document.body,
      )}
    </>
  );
}

export function Tooltip({ label, children, width = 240 }: { label: ReactNode; children: ReactNode; width?: number }) {
  return (
    <Popover content={label} width={width} interactive={false} openDelay={200} className="px-2.5 py-1.5 text-center leading-snug">
      {children}
    </Popover>
  );
}
