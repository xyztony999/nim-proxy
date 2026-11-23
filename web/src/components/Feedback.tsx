import { Alert, Box, CircularProgress, Dialog, DialogContent, DialogTitle, IconButton, TextField, Typography } from "@mui/material";
import ContentCopy from "@mui/icons-material/ContentCopy";
import { useState } from "react";

export function Loading() {
  return (
    <Box sx={{ display: "flex", justifyContent: "center", py: 6 }}>
      <CircularProgress />
    </Box>
  );
}

export function ErrorPanel({ message }: { message: string }) {
  return <Alert severity="error">{message}</Alert>;
}

export function SecretDialog({
  open,
  secret,
  onClose,
}: {
  open: boolean;
  secret: string;
  onClose: () => void;
}) {
  const [copied, setCopied] = useState(false);
  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>密钥已创建</DialogTitle>
      <DialogContent>
        <Alert severity="warning" sx={{ mb: 2 }}>
          完整密钥仅显示这一次，请立即复制保存。
        </Alert>
        <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
          <TextField value={secret} fullWidth slotProps={{ input: { readOnly: true } }} />
          <IconButton
            onClick={() => {
              navigator.clipboard.writeText(secret).then(() => setCopied(true));
            }}
          >
            <ContentCopy />
          </IconButton>
        </Box>
        {copied && (
          <Typography variant="caption" color="success.main">
            已复制
          </Typography>
        )}
      </DialogContent>
    </Dialog>
  );
}
