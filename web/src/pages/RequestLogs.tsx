import {
  Box, Table, TableBody, TableCell, TableContainer, TableHead, TablePagination,
  TableRow, TextField,
} from "@mui/material";
import { useState } from "react";
import { listRequestLogs } from "../api/actions";
import { ErrorPanel, Loading } from "../components/Feedback";
import { Mono, PageHeader, Panel } from "../components/ui";
import { useApi } from "../hooks/useApi";

function statusColor(status: number): string {
  if (status >= 500) return "error.main";
  if (status >= 400) return "warning.main";
  return "success.main";
}

export default function RequestLogs() {
  const [model, setModel] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(20);

  const { data, loading, error } = useApi(
    () => listRequestLogs({ model: model || undefined, status: status || undefined, page_num: page + 1, page_size: pageSize }),
    [model, status, page, pageSize],
  );

  return (
    <Box>
      <PageHeader title="请求日志" subtitle="最近请求明细，保留 30 天" />
      <Panel>
        <Box sx={{ display: "flex", gap: 2, p: 2, flexWrap: "wrap" }}>
          <TextField label="模型" value={model} onChange={(e) => { setModel(e.target.value); setPage(0); }} sx={{ minWidth: 200 }} />
          <TextField label="状态码" value={status} onChange={(e) => { setStatus(e.target.value); setPage(0); }} sx={{ width: 120 }} />
        </Box>
        {loading && <Loading />}
        {error && <ErrorPanel message={error} />}
        {data && (
          <>
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>时间</TableCell>
                    <TableCell>客户端</TableCell>
                    <TableCell>方法</TableCell>
                    <TableCell>路径</TableCell>
                    <TableCell>模型</TableCell>
                    <TableCell>状态</TableCell>
                    <TableCell align="right">延迟</TableCell>
                    <TableCell align="right">tokens</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {data.records.map((r) => (
                    <TableRow key={r.id}>
                      <TableCell><Mono sx={{ fontSize: 12, color: "text.secondary", whiteSpace: "nowrap" }}>{r.ts.replace("T", " ").slice(0, 19)}</Mono></TableCell>
                      <TableCell sx={{ fontSize: 13 }}>{r.client_key_name ?? "—"}</TableCell>
                      <TableCell><Mono sx={{ fontSize: 12 }}>{r.method}</Mono></TableCell>
                      <TableCell><Mono sx={{ fontSize: 12, color: "text.secondary" }}>{r.path}</Mono></TableCell>
                      <TableCell><Mono sx={{ fontSize: 12, color: "text.secondary" }}>{r.model ?? "—"}</Mono></TableCell>
                      <TableCell><Mono sx={{ fontSize: 12.5, color: statusColor(r.status), fontWeight: 600 }}>{r.status}</Mono></TableCell>
                      <TableCell align="right"><Mono sx={{ fontSize: 12, color: "text.secondary" }}>{r.latency_ms}ms</Mono></TableCell>
                      <TableCell align="right"><Mono sx={{ fontSize: 12, color: "text.secondary" }}>{(r.prompt_tokens ?? 0) + (r.completion_tokens ?? 0) || "—"}</Mono></TableCell>
                    </TableRow>
                  ))}
                  {data.records.length === 0 && (
                    <TableRow><TableCell colSpan={8} sx={{ textAlign: "center", color: "text.secondary", py: 5 }}>暂无请求记录</TableCell></TableRow>
                  )}
                </TableBody>
              </Table>
            </TableContainer>
            <TablePagination
              component="div"
              count={data.total}
              page={page}
              onPageChange={(_, p) => setPage(p)}
              rowsPerPage={pageSize}
              onRowsPerPageChange={(e) => { setPageSize(parseInt(e.target.value, 10)); setPage(0); }}
              rowsPerPageOptions={[10, 20, 50, 100]}
            />
          </>
        )}
      </Panel>
    </Box>
  );
}
