import { AppBar, Box, Drawer, IconButton, List, ListItemButton, ListItemText, Toolbar, Tooltip, Typography } from "@mui/material";
import DarkMode from "@mui/icons-material/DarkMode";
import LightMode from "@mui/icons-material/LightMode";
import { Link, Outlet, useLocation, useNavigate } from "react-router-dom";
import { clearToken } from "../api/client";
import { useColorMode } from "../theme/ColorMode";
import Logo from "./Logo";

const NAV = [
  { to: "/", label: "运行看板" },
  { to: "/upstream-keys", label: "上游密钥" },
  { to: "/client-keys", label: "客户端密钥" },
  { to: "/usage", label: "用量统计" },
  { to: "/request-logs", label: "请求日志" },
  { to: "/config", label: "运行配置" },
];

const WIDTH = 200;

export default function Layout() {
  const location = useLocation();
  const navigate = useNavigate();
  const { mode, toggle } = useColorMode();
  return (
    <Box sx={{ display: "flex" }}>
      <AppBar position="fixed" sx={{ zIndex: (t) => t.zIndex.drawer + 1 }}>
        <Toolbar>
          <Box sx={{ mr: 1.5, display: "flex" }}>
            <Logo size={30} />
          </Box>
          <Typography variant="h6" sx={{ flexGrow: 1 }}>
            NIM Proxy 管理台
          </Typography>
          <Tooltip title={mode === "light" ? "切换暗色" : "切换亮色"}>
            <IconButton color="inherit" onClick={toggle} sx={{ mr: 1 }}>
              {mode === "light" ? <DarkMode /> : <LightMode />}
            </IconButton>
          </Tooltip>
          <ListItemButton
            onClick={() => {
              clearToken();
              navigate("/login");
            }}
            sx={{ color: "inherit", flexGrow: 0 }}
          >
            退出
          </ListItemButton>
        </Toolbar>
      </AppBar>
      <Drawer
        variant="permanent"
        sx={{ width: WIDTH, flexShrink: 0, [`& .MuiDrawer-paper`]: { width: WIDTH, boxSizing: "border-box" } }}
      >
        <Toolbar />
        <List>
          {NAV.map((n) => (
            <ListItemButton
              key={n.to}
              component={Link}
              to={n.to}
              selected={location.pathname === n.to}
            >
              <ListItemText primary={n.label} />
            </ListItemButton>
          ))}
        </List>
      </Drawer>
      <Box component="main" sx={{ flexGrow: 1, p: 3 }}>
        <Toolbar />
        <Outlet />
      </Box>
    </Box>
  );
}
