import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { ThemeProvider, createTheme, type Theme } from "@mui/material";

type Mode = "light" | "dark";
const STORAGE_KEY = "nim_theme";

interface ColorMode {
  mode: Mode;
  toggle: () => void;
}

const ColorModeContext = createContext<ColorMode>({ mode: "dark", toggle: () => {} });

export function useColorMode(): ColorMode {
  return useContext(ColorModeContext);
}

function initialMode(): Mode {
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored === "light" || stored === "dark") return stored;
  return window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
}

// "Relay Control" — an NVIDIA NIM operations console.
// Blue-slate layered surfaces (not flat black); NVIDIA green as the live/healthy
// signal, cyan for data, amber/red for warning/error. Grotesk display + Inter UI
// + JetBrains Mono for keys/metrics.
function buildTheme(mode: Mode): Theme {
  const dark = mode === "dark";
  const palette = dark
    ? {
        bg: "#0c1116",
        paper: "#131a22",
        raised: "#1b242e",
        border: "#26313d",
        text: "#e6edf3",
        muted: "#8b98a5",
        green: "#8ed100",
        greenDeep: "#76b900",
        cyan: "#38bdf8",
        amber: "#f5a623",
        red: "#f0564a",
      }
    : {
        bg: "#eef1f4",
        paper: "#ffffff",
        raised: "#f5f7f9",
        border: "#dde3ea",
        text: "#1a222c",
        muted: "#5b6770",
        green: "#5f9600",
        greenDeep: "#4f7d00",
        cyan: "#0284c7",
        amber: "#c77700",
        red: "#d3372c",
      };

  return createTheme({
    palette: {
      mode,
      primary: { main: palette.greenDeep, contrastText: dark ? "#0c1116" : "#ffffff" },
      secondary: { main: palette.cyan },
      success: { main: palette.green },
      warning: { main: palette.amber },
      error: { main: palette.red },
      background: { default: palette.bg, paper: palette.paper },
      text: { primary: palette.text, secondary: palette.muted },
      divider: palette.border,
    },
    shape: { borderRadius: 10 },
    typography: {
      fontFamily: '"Inter", system-ui, sans-serif',
      h1: { fontFamily: '"Space Grotesk", sans-serif', fontWeight: 600 },
      h2: { fontFamily: '"Space Grotesk", sans-serif', fontWeight: 600 },
      h3: { fontFamily: '"Space Grotesk", sans-serif', fontWeight: 600 },
      h4: { fontFamily: '"Space Grotesk", sans-serif', fontWeight: 600, letterSpacing: "-0.01em" },
      h5: { fontFamily: '"Space Grotesk", sans-serif', fontWeight: 600, letterSpacing: "-0.01em" },
      h6: { fontFamily: '"Space Grotesk", sans-serif', fontWeight: 600, letterSpacing: "-0.01em" },
      subtitle2: { fontWeight: 600 },
      button: { textTransform: "none", fontWeight: 600 },
      body2: { lineHeight: 1.6 },
    },
    components: {
      MuiCssBaseline: {
        styleOverrides: {
          body: {
            backgroundColor: palette.bg,
            scrollbarColor: `${palette.border} transparent`,
          },
          "::selection": { backgroundColor: palette.greenDeep, color: dark ? "#0c1116" : "#fff" },
        },
      },
      MuiPaper: {
        styleOverrides: {
          root: { backgroundImage: "none" },
          outlined: { borderColor: palette.border },
        },
        defaultProps: { elevation: 0 },
      },
      MuiButton: {
        defaultProps: { disableElevation: true },
        styleOverrides: {
          root: { borderRadius: 8, paddingInline: 16 },
          containedPrimary: {
            backgroundColor: palette.greenDeep,
            color: dark ? "#0c1116" : "#ffffff",
            "&:hover": { backgroundColor: palette.green },
          },
        },
      },
      MuiTableCell: {
        styleOverrides: {
          root: { borderColor: palette.border, padding: "12px 16px" },
          head: {
            color: palette.muted,
            fontWeight: 600,
            fontSize: 12.5,
            backgroundColor: palette.raised,
            whiteSpace: "nowrap",
          },
        },
      },
      MuiTableRow: {
        styleOverrides: {
          root: { "&:hover": { backgroundColor: palette.raised } },
        },
      },
      MuiChip: {
        styleOverrides: {
          root: { borderRadius: 6, fontWeight: 600, fontFamily: '"JetBrains Mono", monospace', fontSize: 12 },
        },
      },
      MuiTextField: { defaultProps: { size: "small" } },
      MuiTooltip: {
        styleOverrides: { tooltip: { backgroundColor: palette.raised, color: palette.text, border: `1px solid ${palette.border}` } },
      },
    },
  });
}

export function ColorModeProvider({ children }: { children: React.ReactNode }) {
  const [mode, setMode] = useState<Mode>(initialMode);

  useEffect(() => {
    const mq = window.matchMedia("(prefers-color-scheme: light)");
    const onChange = (e: MediaQueryListEvent) => {
      if (!localStorage.getItem(STORAGE_KEY)) setMode(e.matches ? "light" : "dark");
    };
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  const value = useMemo<ColorMode>(
    () => ({
      mode,
      toggle: () =>
        setMode((m) => {
          const next = m === "light" ? "dark" : "light";
          localStorage.setItem(STORAGE_KEY, next);
          return next;
        }),
    }),
    [mode],
  );

  const theme = useMemo(() => buildTheme(mode), [mode]);

  return (
    <ColorModeContext.Provider value={value}>
      <ThemeProvider theme={theme}>{children}</ThemeProvider>
    </ColorModeContext.Provider>
  );
}
