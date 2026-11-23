import {
  Paper, Table, TableBody, TableCell, TableHead, TablePagination, TableRow, TextField, Typography,
} from "@mui/material";
import { useState } from "react";
import { listRequestLogs } from "../api/actions";
import { ErrorPanel, Loading } from "../components/Feedback";
import { useApi } from "../hooks/useApi";

export default function RequestLogs() {
  const [model, setModel] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(20);

  const { data, loading, error } = useApi(
    () =>
      listRequestLogs({
        model: model || undefined,
        status: status || undefined,
        page_num: page + 1,
        page_size: pageSize,
      }),
    [model, status, page, pageSize],
  );

  return (
    <Paper sx={{ p: 2 }}>
      <Typography variant="h6" gutterBottom>
        请求日志（保留 30 天）
      </Typography>
      <TextField
        label="模型"
        size="small"
        value={model}
        onChange={(e) => {
          setModel(e.target.value);
          setPage(0);
        }}
        sx={{ mr: 2 }}
      />
      <TextField
        label="状态码"
        size="small"
        value={status}
        onChange={(e) => {
          setStatus(e.target.value);
          setPage(0);
        }}
      />
      {loading && <Loading />}
      {error && <ErrorPanel message={error} />}
      {data && (
        <>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>时间</TableCell>
                <TableCell>客户端</TableCell>
                <TableCell>上游</TableCell>
                <TableCell>方法</TableCell>
                <TableCell>路径</TableCell>
                <TableCell>模型</TableCell>
                <TableCell>状态</TableCell>
                <TableCell align="right">延迟(ms)</TableCell>
                <TableCell>流式</TableCell>
                <TableCell align="right">tokens</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {data.records.map((r) => (
                <TableRow key={r.id}>
                  <TableCell>{r.ts}</TableCell>
                  <TableCell>{r.client_key_name ?? "—"}</TableCell>
                  <TableCell>{r.upstream_key_label ?? "—"}</TableCell>
                  <TableCell>{r.method}</TableCell>
                  <TableCell>{r.path}</TableCell>
                  <TableCell>{r.model ?? "—"}</TableCell>
                  <TableCell>{r.status}</TableCell>
                  <TableCell align="right">{r.latency_ms}</TableCell>
                  <TableCell>{r.stream ? "是" : "否"}</TableCell>
                  <TableCell align="right">
                    {(r.prompt_tokens ?? 0) + (r.completion_tokens ?? 0) || "—"}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <TablePagination
            component="div"
            count={data.total}
            page={page}
            onPageChange={(_, p) => setPage(p)}
            rowsPerPage={pageSize}
            onRowsPerPageChange={(e) => {
              setPageSize(parseInt(e.target.value, 10));
              setPage(0);
            }}
            rowsPerPageOptions={[10, 20, 50, 100]}
          />
        </>
      )}
    </Paper>
  );
}
