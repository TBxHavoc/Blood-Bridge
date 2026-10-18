import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { AuthProvider } from "./auth/AuthContext";
import { App } from "./App";
import "./styles/tokens.css";
import "./styles/app.css";
import "./styles/login.css";

const container = document.getElementById("root");
if (!container) throw new Error("Root element #root not found");

createRoot(container).render(
  <StrictMode>
    <AuthProvider>
      <App />
    </AuthProvider>
  </StrictMode>,
);
