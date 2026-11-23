import {
  AppBar, Box, Divider, Drawer, IconButton, List, ListItemButton, ListItemIcon,
  ListItemText, Toolbar, Tooltip, Typography, useMediaQuery, useTheme,
} from "@mui/material";
import BarChart from "@mui/icons-material/BarChart";
import DarkMode from "@mui/icons-material/DarkMode";
import Key from "@mui/icons-material/Key";
import LightMode from "@mui/icons-material/LightMode";
import Logout from "@mui/icons-material/Logout";
import MenuIcon from "@mui/icons-material/Menu";
import ReceiptLong from "@mui/icons-material/ReceiptLong";
import SpaceDashboard from "@mui/icons-material/SpaceDashboard";
import Tune from "@mui/icons-material/Tune";
import VpnKey from "@mui/icons-material/VpnKey";
import { useState } from "react";
import { Link, Outlet, useLocation, useNavigate } from "react-router-dom";
import { clearToken } from "../api/client";
import { useColorMode } from "../theme/ColorMode";
import Logo from "./Logo";

const NAV = [
  { to: "/", label: "运行看板", icon: <SpaceDashboard fontSize="small" /> },
  { to: "/upstream-keys", label: "上游密钥", icon: <VpnKey fontSize="small" /> },
  { to: "/client-keys", label: "客户端密钥", icon: <Key fontSize="small" /> },
  { to: "/usage", label: "用量统计", icon: <BarChart fontSize="small" /> },
  { to: "/request-logs", label: "请求日志", icon: <ReceiptLong fontSize="small" /> },
  { to: "/config", label: "运行配置", icon: <Tune fontSize="small" /> },
];

const WIDTH = 244;

function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  const location = useLocation();
  const navigate = useNavigate();
  const { mode, toggle } = useColorMode();
  return (
    <Box sx={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <Box sx={{ display: "flex", alignItems: "center", gap: 1.5, px: 2.5, py: 2.5 }}>
        <Logo size={34} />
        <Box>
          <Typography sx={{ fontFamily: '"Space Grotesk", sans-serif', fontWeight: 700, lineHeight: 1.1 }}>
            NIM Proxy
          </Typography>
          <Typography variant="caption" color="text.secondary">
            中继管理台
          </Typography>
        </Box>
      </Box>
      <Divider />
      <List sx={{ px: 1.5, py: 1.5, flexGrow: 1 }}>
        {NAV.map((n) => {
          const active = location.pathname === n.to;
          return (
            <ListItemButton
              key={n.to}
              component={Link}
              to={n.to}
              onClick={onNavigate}
              selected={active}
              sx={{
                borderRadius: 2,
                mb: 0.5,
                py: 1,
                position: "relative",
                color: active ? "success.main" : "text.secondary",
                "&.Mui-selected": { backgroundColor: "action.selected" },
                "&.Mui-selected:hover": { backgroundColor: "action.hover" },
                "&::before": active
                  ? { content: '""', position: "absolute", left: -12, top: 8, bottom: 8, width: 3, borderRadius: 2, backgroundColor: "success.main" }
                  : {},
              }}
            >
              <ListItemIcon sx={{ minWidth: 34, color: "inherit" }}>{n.icon}</ListItemIcon>
              <ListItemText primary={n.label} primaryTypographyProps={{ fontSize: 14, fontWeight: active ? 600 : 500 }} />
            </ListItemButton>
          );
        })}
      </List>
      <Divider />
      <Box sx={{ px: 2, py: 1.5, display: "flex", alignItems: "center", gap: 1 }}>
        <Box sx={{ display: "flex", alignItems: "center", gap: 0.75, flexGrow: 1 }}>
          <Box sx={{ width: 7, height: 7, borderRadius: "50%", backgroundColor: "success.main", boxShadow: (t) => `0 0 8px ${t.palette.success.main}` }} />
          <Typography variant="caption" color="text.secondary">运行中</Typography>
        </Box>
        <Tooltip title={mode === "dark" ? "切换亮色" : "切换暗色"}>
          <IconButton size="small" onClick={toggle} aria-label="切换主题">
            {mode === "dark" ? <LightMode fontSize="small" /> : <DarkMode fontSize="small" />}
          </IconButton>
        </Tooltip>
        <Tooltip title="退出登录">
          <IconButton size="small" aria-label="退出登录" onClick={() => { clearToken(); navigate("/login"); }}>
            <Logout fontSize="small" />
          </IconButton>
        </Tooltip>
      </Box>
    </Box>
  );
}

export default function Layout() {
  const theme = useTheme();
  const isDesktop = useMediaQuery(theme.breakpoints.up("md"));
  const [open, setOpen] = useState(false);

  return (
    <Box sx={{ display: "flex", minHeight: "100vh" }}>
      {isDesktop ? (
        <Drawer variant="permanent" sx={{ width: WIDTH, flexShrink: 0, "& .MuiDrawer-paper": { width: WIDTH, boxSizing: "border-box", borderRight: "1px solid", borderColor: "divider", backgroundColor: "background.paper" } }}>
          <SidebarContent />
        </Drawer>
      ) : (
        <>
          <AppBar position="fixed" color="inherit" elevation={0} sx={{ borderBottom: "1px solid", borderColor: "divider", backgroundColor: "background.paper" }}>
            <Toolbar>
              <IconButton edge="start" aria-label="打开菜单" onClick={() => setOpen(true)} sx={{ mr: 1 }}>
                <MenuIcon />
              </IconButton>
              <Logo size={26} />
              <Typography sx={{ ml: 1, fontFamily: '"Space Grotesk", sans-serif', fontWeight: 700 }}>NIM Proxy</Typography>
            </Toolbar>
          </AppBar>
          <Drawer open={open} onClose={() => setOpen(false)} sx={{ "& .MuiDrawer-paper": { width: WIDTH, backgroundColor: "background.paper" } }}>
            <SidebarContent onNavigate={() => setOpen(false)} />
          </Drawer>
        </>
      )}
      <Box component="main" sx={{ flexGrow: 1, minWidth: 0, px: { xs: 2, md: 4 }, py: { xs: 2, md: 4 }, pt: { xs: 9, md: 4 } }}>
        <Box sx={{ maxWidth: 1160, mx: "auto" }}>
          <Outlet />
        </Box>
      </Box>
    </Box>
  );
}
