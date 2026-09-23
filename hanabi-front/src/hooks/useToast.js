import { useState, useRef, useEffect, useCallback } from "react";

const VISIBLE_MS = 2400;
const VISIBLE_ACTION_MS = 6000;

/** Notification a un seul message : un nouveau remplace le precedent et relance le minuteur. */
export function useToast() {
  const [toast, setToast] = useState(null);
  const timer = useRef(null);

  const hide = useCallback(() => {
    clearTimeout(timer.current);
    setToast(null);
  }, []);

  const show = useCallback((message, action = null) => {
    setToast({ message, action });
    clearTimeout(timer.current);
    timer.current = setTimeout(() => setToast(null), action ? VISIBLE_ACTION_MS : VISIBLE_MS);
  }, []);

  const runAction = useCallback(() => {
    toast?.action?.run();
    hide();
  }, [toast, hide]);

  useEffect(() => () => clearTimeout(timer.current), []);

  return { toast, show, hide, runAction };
}
