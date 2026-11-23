import { Alert, Box, Button, Paper, TextField, Typography } from "@mui/material";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { login } from "../api/actions";
import { setToken } from "../api/client";
import Logo from "../components/Logo";

export default function Login() {
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      const { token } = await login(password);
      setToken(token);
      navigate("/");
    } catch (e) {
      setError(e instanceof Error ? e.message : "登录失败");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Box
      sx={{
        display: "flex", justifyContent: "center", alignItems: "center", minHeight: "100vh", p: 2,
        backgroundImage: (t) => `linear-gradient(${t.palette.divider} 1px, transparent 1px), linear-gradient(90deg, ${t.palette.divider} 1px, transparent 1px)`,
        backgroundSize: "32px 32px",
      }}
    >
      <Paper variant="outlined" sx={{ p: 4, width: 380, borderRadius: 3 }}>
        <Box sx={{ display: "flex", justifyContent: "center", mb: 2 }}>
          <Logo size={56} />
        </Box>
        <Typography variant="h6" gutterBottom align="center">
          NIM Proxy 管理台
        </Typography>
        <Typography variant="body2" color="text.secondary" gutterBottom>
          输入管理员密码（或 env 管理令牌）登录
        </Typography>
        <TextField
          label="密码 / 令牌"
          type="password"
          fullWidth
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          sx={{ my: 2 }}
          onKeyDown={(e) => e.key === "Enter" && submit()}
        />
        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}
        <Button variant="contained" fullWidth disabled={busy || !password} onClick={submit}>
          {busy ? "登录中…" : "登录"}
        </Button>
      </Paper>
    </Box>
  );
}
