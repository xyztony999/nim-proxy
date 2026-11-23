import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { CssBaseline } from "@mui/material";
import App from "./App";
import { ColorModeProvider } from "./theme/ColorMode";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ColorModeProvider>
      <CssBaseline />
      <BrowserRouter basename="/admin">
        <App />
      </BrowserRouter>
    </ColorModeProvider>
  </StrictMode>,
);
