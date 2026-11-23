import { Box, Paper, Typography, type SxProps, type Theme } from "@mui/material";
import type { ReactNode } from "react";

export function Mono({ children, sx }: { children: ReactNode; sx?: SxProps<Theme> }) {
  return (
    <Box component="span" sx={{ fontFamily: '"JetBrains Mono", monospace', ...sx }}>
      {children}
    </Box>
  );
}

export function PageHeader({
  title,
  subtitle,
  action,
}: {
  title: string;
  subtitle?: string;
  action?: ReactNode;
}) {
  return (
    <Box sx={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between", gap: 2, mb: 3, flexWrap: "wrap" }}>
      <Box>
        <Typography variant="h4">{title}</Typography>
        {subtitle && (
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
            {subtitle}
          </Typography>
        )}
      </Box>
      {action}
    </Box>
  );
}

export function Panel({ children, sx }: { children: ReactNode; sx?: SxProps<Theme> }) {
  return (
    <Paper variant="outlined" sx={{ borderRadius: 3, overflow: "hidden", ...sx }}>
      {children}
    </Paper>
  );
}

export function StatTile({
  label,
  value,
  accent,
  hint,
}: {
  label: string;
  value: ReactNode;
  accent?: string;
  hint?: string;
}) {
  return (
    <Paper variant="outlined" sx={{ p: 2.5, borderRadius: 3, position: "relative", overflow: "hidden" }}>
      <Box sx={{ position: "absolute", left: 0, top: 0, bottom: 0, width: 3, backgroundColor: accent ?? "divider" }} />
      <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
        {label}
      </Typography>
      <Typography variant="h4" sx={{ fontFamily: '"JetBrains Mono", monospace', color: accent ?? "text.primary" }}>
        {value}
      </Typography>
      {hint && (
        <Typography variant="caption" color="text.secondary">
          {hint}
        </Typography>
      )}
    </Paper>
  );
}

const STATUS_COLOR: Record<string, string> = {
  enabled: "success.main",
  disabled: "text.secondary",
  revoked: "error.main",
};

export function StatusChip({ status }: { status: string }) {
  const label = status === "enabled" ? "启用" : status === "disabled" ? "停用" : "已撤销";
  const color = STATUS_COLOR[status] ?? "text.secondary";
  return (
    <Box
      component="span"
      sx={{
        display: "inline-flex",
        alignItems: "center",
        gap: 0.75,
        px: 1,
        py: 0.25,
        borderRadius: 1.5,
        border: "1px solid",
        borderColor: "divider",
        fontFamily: '"JetBrains Mono", monospace',
        fontSize: 12,
        color,
      }}
    >
      <Box sx={{ width: 6, height: 6, borderRadius: "50%", backgroundColor: "currentColor" }} />
      {label}
    </Box>
  );
}

// The characteristic element: client -> proxy -> NIM relay pipeline.
export function RelayPipeline({ live = true }: { live?: boolean }) {
  const node = (label: string, sub: string, color: string) => (
    <Box sx={{ textAlign: "center", minWidth: 96 }}>
      <Box
        sx={{
          width: 44,
          height: 44,
          mx: "auto",
          mb: 1,
          borderRadius: 2,
          border: "1px solid",
          borderColor: "divider",
          backgroundColor: "background.paper",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color,
          fontFamily: '"JetBrains Mono", monospace',
          fontWeight: 600,
        }}
      >
        {label}
      </Box>
      <Typography variant="caption" color="text.secondary">
        {sub}
      </Typography>
    </Box>
  );
  const wire = (
    <Box sx={{ flex: 1, height: 2, minWidth: 32, position: "relative", backgroundColor: "divider", borderRadius: 1 }}>
      <Box
        sx={{
          position: "absolute",
          inset: 0,
          borderRadius: 1,
          background: (t) => `linear-gradient(90deg, transparent, ${t.palette.success.main}, transparent)`,
          opacity: live ? 0.9 : 0.2,
          animation: live ? "nim-flow 2.4s linear infinite" : "none",
          "@keyframes nim-flow": { "0%": { transform: "translateX(-100%)" }, "100%": { transform: "translateX(100%)" } },
          "@media (prefers-reduced-motion: reduce)": { animation: "none" },
        }}
      />
    </Box>
  );
  return (
    <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
      {node("CLI", "客户端", "text.primary")}
      {wire}
      {node("NIM", "代理", "success.main")}
      {wire}
      {node("GPU", "NVIDIA NIM", "secondary.main")}
    </Box>
  );
}
