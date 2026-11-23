import {
  Button, Dialog, DialogActions, DialogContent, DialogTitle, IconButton, Paper,
  Table, TableBody, TableCell, TableHead, TableRow, TextField, Tooltip, Typography,
} from "@mui/material";
import Delete from "@mui/icons-material/Delete";
import { useState } from "react";
import {
  createClientKey, disableClientKey, enableClientKey, listClientKeys, revokeClientKey,
} from "../api/actions";
import { ErrorPanel, Loading, SecretDialog } from "../components/Feedback";
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
    <Paper sx={{ p: 2 }}>
      <Typography variant="h6" gutterBottom>
        客户端密钥
        <Button variant="contained" sx={{ float: "right" }} onClick={() => setOpen(true)}>
          签发
        </Button>
      </Typography>
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>名称</TableCell>
            <TableCell>密钥（脱敏）</TableCell>
            <TableCell>状态</TableCell>
            <TableCell>最近使用</TableCell>
            <TableCell align="right">操作</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {data?.map((k) => {
            const revoked = k.revoked_at !== null;
            return (
              <TableRow key={k.id}>
                <TableCell>{k.name}</TableCell>
                <TableCell>{k.secret_masked}</TableCell>
                <TableCell>{revoked ? "已撤销" : k.enabled ? "启用" : "停用"}</TableCell>
                <TableCell>{k.last_used_at ?? "—"}</TableCell>
                <TableCell align="right">
                  <Button
                    size="small"
                    disabled={revoked}
                    onClick={async () => {
                      await (k.enabled ? disableClientKey(k.id) : enableClientKey(k.id));
                      reload();
                    }}
                  >
                    {k.enabled ? "停用" : "启用"}
                  </Button>
                  <Tooltip title="撤销">
                    <IconButton
                      size="small"
                      disabled={revoked}
                      onClick={async () => {
                        await revokeClientKey(k.id);
                        reload();
                      }}
                    >
                      <Delete fontSize="small" />
                    </IconButton>
                  </Tooltip>
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>

      <Dialog open={open} onClose={() => setOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>签发客户端密钥</DialogTitle>
        <DialogContent>
          <TextField label="名称 / 备注" fullWidth value={name} onChange={(e) => setName(e.target.value)} sx={{ my: 1 }} />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpen(false)}>取消</Button>
          <Button variant="contained" disabled={busy || !name} onClick={create}>
            保存
          </Button>
        </DialogActions>
      </Dialog>

      <SecretDialog open={created !== null} secret={created ?? ""} onClose={() => setCreated(null)} />
    </Paper>
  );
}
