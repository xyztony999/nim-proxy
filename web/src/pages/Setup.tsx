import {
  Alert, Box, Button, Paper, Step, StepLabel, Stepper, TextField, Typography,
} from "@mui/material";
import { useState } from "react";
import { setupInit } from "../api/actions";
import { SecretDialog } from "../components/Feedback";

export default function Setup({ onDone }: { onDone: () => void }) {
  const [nvidiaKey, setNvidiaKey] = useState("");
  const [password, setPassword] = useState("");
  const [clientName, setClientName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [finished, setFinished] = useState(false);
  const [clientSecret, setClientSecret] = useState<string | null>(null);

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      const res = await setupInit({
        nvidia_key: nvidiaKey,
        admin_password: password,
        client_key_name: clientName || undefined,
      });
      setClientSecret(res.client_secret);
      setFinished(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "初始化失败");
    } finally {
      setBusy(false);
    }
  };

  const valid = nvidiaKey.startsWith("nvapi-") && password.length >= 8;

  return (
    <Box sx={{ display: "flex", justifyContent: "center", alignItems: "center", minHeight: "100vh", p: 2 }}>
      <Paper sx={{ p: 4, maxWidth: 520, width: "100%" }}>
        <Typography variant="h5" gutterBottom>
          欢迎使用 NIM Proxy
        </Typography>
        <Typography variant="body2" color="text.secondary" gutterBottom>
          首次使用请完成初始化。填入你的 NVIDIA 密钥以验证所有权，并设置管理员密码。
        </Typography>
        <Stepper activeStep={0} sx={{ my: 2 }}>
          <Step completed><StepLabel>验证密钥</StepLabel></Step>
          <Step completed={false}><StepLabel>设管理员密码</StepLabel></Step>
          <Step completed={false}><StepLabel>完成</StepLabel></Step>
        </Stepper>

        <TextField
          label="NVIDIA 密钥（nvapi-…）"
          fullWidth
          value={nvidiaKey}
          onChange={(e) => setNvidiaKey(e.target.value)}
          sx={{ my: 1 }}
          helperText="将向 NIM 验证此密钥以确认所有权，并存为上游密钥"
        />
        <TextField
          label="管理员密码（至少 8 位）"
          type="password"
          fullWidth
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          sx={{ my: 1 }}
        />
        <TextField
          label="客户端密钥名称（可选，自动签发）"
          fullWidth
          value={clientName}
          onChange={(e) => setClientName(e.target.value)}
          sx={{ my: 1 }}
        />
        {error && <Alert severity="error" sx={{ my: 1 }}>{error}</Alert>}
        <Button variant="contained" fullWidth disabled={busy || !valid} onClick={submit} sx={{ mt: 2 }}>
          {busy ? "验证并初始化…" : "完成初始化"}
        </Button>
      </Paper>

      <SecretDialog
        open={finished && !!clientSecret}
        secret={clientSecret ?? ""}
        onClose={onDone}
      />
      {finished && !clientSecret && (
        <Box sx={{ position: "fixed", bottom: 24, left: 0, right: 0, display: "flex", justifyContent: "center" }}>
          <Button variant="contained" onClick={onDone}>初始化完成，进入登录</Button>
        </Box>
      )}
    </Box>
  );
}
