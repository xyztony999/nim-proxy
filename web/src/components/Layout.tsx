import { AppBar, Box, Drawer, List, ListItemButton, ListItemText, Toolbar, Typography } from "@mui/material";
import { Link, Outlet, useLocation, useNavigate } from "react-router-dom";
import { clearToken } from "../api/client";

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
  return (
    <Box sx={{ display: "flex" }}>
      <AppBar position="fixed" sx={{ zIndex: (t) => t.zIndex.drawer + 1 }}>
        <Toolbar>
          <Typography variant="h6" sx={{ flexGrow: 1 }}>
            NIM Proxy 管理台
          </Typography>
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
