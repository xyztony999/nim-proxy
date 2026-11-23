import {
  Box, Button, Dialog, DialogActions, DialogContent, DialogTitle, IconButton,
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow, TextField, Tooltip,
} from "@mui/material";
import Add from "@mui/icons-material/Add";
import DeleteOutline from "@mui/icons-material/DeleteOutline";
import { useState } from "react";
import {
  createClientKey, disableClientKey, enableClientKey, listClientKeys, revokeClientKey,
} from "../api/actions";
import { ErrorPanel, Loading, SecretDialog } from "../components/Feedback";
import { Mono, PageHeader, Panel, StatusChip } from "../components/ui";
import { fmtLocal } from "../lib/format";
import { useApi } from "../hooks/useApi";

export default function ClientKeys() {
  const { data, loading, error, reload } = useApi(listClientKeys);
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [created, setCreated] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const create = async () => {
    setBusy(true);
    try {
      const k = await createClientKey(name);
      setOpen(false);
      setName("");
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
        title="客户端密钥"
        subtitle="客户端访问代理的凭证；完整值仅在签发时显示一次"
        action={<Button variant="contained" startIcon={<Add />} onClick={() => setOpen(true)}>签发密钥</Button>}
      />
      <Panel>
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>名称</TableCell>
                <TableCell>密钥</TableCell>
                <TableCell>状态</TableCell>
                <TableCell>最近使用</TableCell>
                <TableCell align="right">操作</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {data?.map((k) => {
                const revoked = k.revoked_at !== null;
                const status = revoked ? "revoked" : k.enabled ? "enabled" : "disabled";
                return (
                  <TableRow key={k.id}>
                    <TableCell sx={{ fontWeight: 600 }}>{k.name}</TableCell>
                    <TableCell><Mono sx={{ fontSize: 13, color: "text.secondary" }}>{k.secret_masked}</Mono></TableCell>
                    <TableCell><StatusChip status={status} /></TableCell>
                    <TableCell><Mono sx={{ fontSize: 12.5, color: "text.secondary" }}>{fmtLocal(k.last_used_at)}</Mono></TableCell>
                    <TableCell align="right">
                      <Button size="small" disabled={revoked} onClick={async () => { await (k.enabled ? disableClientKey(k.id) : enableClientKey(k.id)); reload(); }}>
                        {k.enabled ? "停用" : "启用"}
                      </Button>
                      <Tooltip title="撤销">
                        <IconButton size="small" disabled={revoked} aria-label="撤销" onClick={async () => { await revokeClientKey(k.id); reload(); }}>
                          <DeleteOutline fontSize="small" />
                        </IconButton>
                      </Tooltip>
                    </TableCell>
                  </TableRow>
                );
              })}
              {data?.length === 0 && (
                <TableRow><TableCell colSpan={5} sx={{ textAlign: "center", color: "text.secondary", py: 5 }}>还没有客户端密钥，点击右上角签发</TableCell></TableRow>
              )}
            </TableBody>
          </Table>
        </TableContainer>
      </Panel>

      <Dialog open={open} onClose={() => setOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>签发客户端密钥</DialogTitle>
        <DialogContent>
          <TextField label="名称 / 备注" fullWidth value={name} onChange={(e) => setName(e.target.value)} sx={{ my: 1 }} />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpen(false)}>取消</Button>
          <Button variant="contained" disabled={busy || !name} onClick={create}>保存</Button>
        </DialogActions>
      </Dialog>

      <SecretDialog open={created !== null} secret={created ?? ""} onClose={() => setCreated(null)} />
    </Box>
  );
}
