import { useAuth } from "./auth/AuthContext";
import { Login } from "./pages/Login";
import { Dashboard } from "./pages/Dashboard";

export function App() {
  const { user, token, loading } = useAuth();

  if (loading) {
    return (
      <div className="blank" style={{ minHeight: "100vh", border: 0, borderRadius: 0 }}>
        Loading Blood Bridge…
      </div>
    );
  }

  if (!user || !token) return <Login />;

  return <Dashboard token={token} user={user} />;
}
