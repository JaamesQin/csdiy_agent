import "highlight.js/styles/github.css";
import "./styles.css";

import { createRoot } from "react-dom/client";

import App from "./App";

try {
  sessionStorage.removeItem("coursepilot_api_key");
  sessionStorage.removeItem("coursepilot_api_base");
  localStorage.removeItem("coursepilot_anonymous_user");
} catch {
  // Storage can be disabled by browser policy; the app does not depend on it.
}

const rootElement = document.querySelector<HTMLElement>("#root");
if (!rootElement) throw new Error("Missing required UI element: #root");

createRoot(rootElement).render(<App />);
