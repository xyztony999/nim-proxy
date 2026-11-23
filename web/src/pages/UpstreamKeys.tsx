import {
  Box, Button, Dialog, DialogActions, DialogContent, DialogTitle, IconButton,
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow, TextField, Tooltip,
} from "@mui/material";
import Add from "@mui/icons-material/Add";
import DeleteOutline from "@mui/icons-material/DeleteOutline";
import { useState } from "react";
import {
  createUpstreamKey, deleteUpstreamKey, disableUpstreamKey, enableUpstreamKey, listUpstreamKeys,
} from "../api/actions";
import { ErrorPanel, Loading, SecretDialog } from "../components/Feedback";
import { Mono, PageHeader, Panel, StatusChip } from "../components/ui";
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
    <Box>
      <PageHeader
        title="上游密钥"
        subtitle="NVIDIA NIM 真实密钥，仅存服务端；停用后不参与轮询"
        action={<Button variant="contained" startIcon={<Add />} onClick={() => setOpen(true)}>新增密钥</Button>}
      />
      <Panel>
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>标签</TableCell>
                <TableCell>密钥</TableCell>
                <TableCell>状态</TableCell>
                <TableCell>最近错误</TableCell>
                <TableCell>连续失败</TableCell>
                <TableCell align="right">操作</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {data?.map((k) => (
                <TableRow key={k.id}>
                  <TableCell sx={{ fontWeight: 600 }}>{k.label}</TableCell>
                  <TableCell><Mono sx={{ fontSize: 13, color: "text.secondary" }}>{k.secret_masked}</Mono></TableCell>
                  <TableCell><StatusChip status={k.enabled ? "enabled" : "disabled"} /></TableCell>
                  <TableCell><Mono sx={{ fontSize: 13, color: k.last_error_status ? "error.main" : "text.secondary" }}>{k.last_error_status ?? "—"}</Mono></TableCell>
                  <TableCell><Mono sx={{ fontSize: 13, color: k.consecutive_failures > 0 ? "warning.main" : "text.secondary" }}>{k.consecutive_failures}</Mono></TableCell>
                  <TableCell align="right">
                    <Button size="small" onClick={async () => { await (k.enabled ? disableUpstreamKey(k.id) : enableUpstreamKey(k.id)); reload(); }}>
                      {k.enabled ? "停用" : "启用"}
                    </Button>
                    <Tooltip title="删除">
                      <IconButton size="small" aria-label="删除" onClick={async () => { await deleteUpstreamKey(k.id); reload(); }}>
                        <DeleteOutline fontSize="small" />
                      </IconButton>
                    </Tooltip>
                  </TableCell>
                </TableRow>
              ))}
              {data?.length === 0 && (
                <TableRow><TableCell colSpan={6} sx={{ textAlign: "center", color: "text.secondary", py: 5 }}>还没有上游密钥，点击右上角新增</TableCell></TableRow>
              )}
            </TableBody>
          </Table>
        </TableContainer>
      </Panel>

      <Dialog open={open} onClose={() => setOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>新增上游密钥</DialogTitle>
        <DialogContent>
          <TextField label="标签" fullWidth value={label} onChange={(e) => setLabel(e.target.value)} sx={{ my: 1 }} />
          <TextField label="NVIDIA 密钥（nvapi-…）" fullWidth value={secret} onChange={(e) => setSecret(e.target.value)} sx={{ my: 1 }} />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpen(false)}>取消</Button>
          <Button variant="contained" disabled={busy || !label || !secret.startsWith("nvapi-")} onClick={create}>保存</Button>
        </DialogActions>
      </Dialog>

      <SecretDialog open={created !== null} secret={created ?? ""} onClose={() => setCreated(null)} />
    </Box>
  );
}
