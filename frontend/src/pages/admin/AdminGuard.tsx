import { useAuthStore } from "@/lib/store";

const READ_ROLES = new Set(["Admin", "Ops", "Support", "ReadOnly"]);

export function AdminGuard({ children }: { children: React.ReactNode }) {
  const { user } = useAuthStore();

  if (!user || !READ_ROLES.has(user.role)) {
    return (
      <div className="panel">
        <h2 className="status status-danger" style={{ marginTop: 0 }}>
          Admin access required
        </h2>
        <p className="muted">Contact an administrator to request access.</p>
      </div>
    );
  }

  return <>{children}</>;
}
