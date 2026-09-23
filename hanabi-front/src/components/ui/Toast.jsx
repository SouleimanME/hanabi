/** Notification breve, annoncee sans interrompre la lecture. */
export function Toast({ toast, onAction }) {
  const message = toast?.message;
  return (
    <div className="toast" data-open={Boolean(message)} role="status" aria-live="polite">
      {message && <span>{message}</span>}
      {toast?.action && (
        <button className="toast-action" onClick={onAction}>
          {toast.action.label}
        </button>
      )}
    </div>
  );
}
