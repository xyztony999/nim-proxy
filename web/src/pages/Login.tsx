import { Alert, Box, Button, Paper, TextField, Typography } from "@mui/material";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { getDashboard } from "../api/actions";
import { setToken } from "../api/client";

export default function Login() {
  const [token, setTokenInput] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();

  const submit = async () => {
    setBusy(true);
    setError(null);
    setToken(token);
    try {
      await getDashboard();
      navigate("/");
    } catch (e) {
      setError(e instanceof Error ? e.message : "登录失败");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Box sx={{ display: "flex", justifyContent: "center", alignItems: "center", minHeight: "100vh" }}>
      <Paper sx={{ p: 4, width: 360 }}>
        <Typography variant="h6" gutterBottom>
          NIM Proxy 管理台
        </Typography>
        <Typography variant="body2" color="text.secondary" gutterBottom>
          输入管理令牌（ADMIN_TOKEN）登录
        </Typography>
        <TextField
          label="管理令牌"
          type="password"
          fullWidth
          value={token}
          onChange={(e) => setTokenInput(e.target.value)}
          sx={{ my: 2 }}
          onKeyDown={(e) => e.key === "Enter" && submit()}
        />
        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}
        <Button variant="contained" fullWidth disabled={busy || !token} onClick={submit}>
          {busy ? "验证中…" : "登录"}
        </Button>
      </Paper>
    </Box>
  );
}
