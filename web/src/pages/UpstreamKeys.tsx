import {
  Button, Dialog, DialogActions, DialogContent, DialogTitle, IconButton, Paper,
  Table, TableBody, TableCell, TableHead, TableRow, TextField, Tooltip, Typography,
} from "@mui/material";
import Delete from "@mui/icons-material/Delete";
import { useState } from "react";
import {
  createUpstreamKey, deleteUpstreamKey, disableUpstreamKey, enableUpstreamKey, listUpstreamKeys,
} from "../api/actions";
import { ErrorPanel, Loading, SecretDialog } from "../components/Feedback";
import { useApi } from "../hooks/useApi";

export default function UpstreamKeys() {
  const { data, loading, error, reload } = useApi(listUpstreamKeys);
  const [open, setOpen] = useState(false);
  const [label, setLabel] = useState("");
  const [secret, setSecret] = useState("");
  const [created, setCreated] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const create = async () => {
    setBusy(true);
    try {
      const k = await createUpstreamKey(label, secret);
      setOpen(false);
      setLabel("");
      setSecret("");
      setCreated(k.secret ?? null);
      reload();
    } finally {
      setBusy(false);
    }
  };

  if (loading) return <Loading />;
  if (error) return <ErrorPanel message={error} />;

  return (
    <Paper sx={{ p: 2 }}>
      <Typography variant="h6" gutterBottom>
        上游密钥
        <Button variant="contained" sx={{ float: "right" }} onClick={() => setOpen(true)}>
          新增
        </Button>
      </Typography>
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>标签</TableCell>
            <TableCell>密钥（脱敏）</TableCell>
            <TableCell>状态</TableCell>
            <TableCell>最近错误</TableCell>
            <TableCell>连续失败</TableCell>
            <TableCell align="right">操作</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {data?.map((k) => (
            <TableRow key={k.id}>
              <TableCell>{k.label}</TableCell>
              <TableCell>{k.secret_masked}</TableCell>
              <TableCell>{k.enabled ? "启用" : "停用"}</TableCell>
              <TableCell>{k.last_error_status ?? "—"}</TableCell>
              <TableCell>{k.consecutive_failures}</TableCell>
              <TableCell align="right">
                <Button
                  size="small"
                  onClick={async () => {
                    await (k.enabled ? disableUpstreamKey(k.id) : enableUpstreamKey(k.id));
                    reload();
                  }}
                >
                  {k.enabled ? "停用" : "启用"}
                </Button>
                <Tooltip title="删除">
                  <IconButton
                    size="small"
                    onClick={async () => {
                      await deleteUpstreamKey(k.id);
                      reload();
                    }}
                  >
                    <Delete fontSize="small" />
                  </IconButton>
                </Tooltip>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      <Dialog open={open} onClose={() => setOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>新增上游密钥</DialogTitle>
        <DialogContent>
          <TextField label="标签" fullWidth value={label} onChange={(e) => setLabel(e.target.value)} sx={{ my: 1 }} />
          <TextField
            label="NVIDIA 密钥（nvapi-…）"
            fullWidth
            value={secret}
            onChange={(e) => setSecret(e.target.value)}
            sx={{ my: 1 }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpen(false)}>取消</Button>
          <Button variant="contained" disabled={busy || !label || !secret.startsWith("nvapi-")} onClick={create}>
            保存
          </Button>
        </DialogActions>
      </Dialog>

      <SecretDialog open={created !== null} secret={created ?? ""} onClose={() => setCreated(null)} />
    </Paper>
  );
}
