import {
  Box, Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
  ToggleButton, ToggleButtonGroup, useTheme,
} from "@mui/material";
import { useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { getUsage } from "../api/actions";
import { ErrorPanel, Loading } from "../components/Feedback";
import { Mono, PageHeader, Panel } from "../components/ui";
import { useApi } from "../hooks/useApi";

export default function Usage() {
  const theme = useTheme();
  const [dimension, setDimension] = useState("key");
  const [bucket, setBucket] = useState("day");
  const { data, loading, error } = useApi(
    () => getUsage({ dimension_type: dimension, bucket_type: bucket }),
    [dimension, bucket],
  );

  return (
    <Box>
      <PageHeader title="用量统计" subtitle="按密钥 / 模型 / 状态维度的请求量与 token（尽力统计）" />
      <Panel sx={{ p: 2.5 }}>
        <Box sx={{ display: "flex", gap: 2, mb: 2, flexWrap: "wrap" }}>
          <ToggleButtonGroup size="small" exclusive value={dimension} onChange={(_, v) => v && setDimension(v)}>
            <ToggleButton value="key">按密钥</ToggleButton>
            <ToggleButton value="model">按模型</ToggleButton>
            <ToggleButton value="status">按状态码</ToggleButton>
          </ToggleButtonGroup>
          <ToggleButtonGroup size="small" exclusive value={bucket} onChange={(_, v) => v && setBucket(v)}>
            <ToggleButton value="hour">小时</ToggleButton>
            <ToggleButton value="day">天</ToggleButton>
          </ToggleButtonGroup>
        </Box>

        {loading && <Loading />}
        {error && <ErrorPanel message={error} />}
        {data && (
          <>
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={theme.palette.divider} />
                <XAxis dataKey="dimension_value" tick={{ fill: theme.palette.text.secondary, fontSize: 12 }} stroke={theme.palette.divider} />
                <YAxis allowDecimals={false} tick={{ fill: theme.palette.text.secondary, fontSize: 12 }} stroke={theme.palette.divider} />
                <Tooltip
                  contentStyle={{ backgroundColor: theme.palette.background.paper, border: `1px solid ${theme.palette.divider}`, borderRadius: 8, color: theme.palette.text.primary }}
                />
                <Legend />
                <Bar dataKey="requests" name="请求" fill={theme.palette.secondary.main} radius={[3, 3, 0, 0]} />
                <Bar dataKey="errors" name="错误" fill={theme.palette.error.main} radius={[3, 3, 0, 0]} />
                <Bar dataKey="rate_limited" name="429" fill={theme.palette.warning.main} radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
            <TableContainer sx={{ mt: 2 }}>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>时段</TableCell>
                    <TableCell>维度值</TableCell>
                    <TableCell align="right">请求</TableCell>
                    <TableCell align="right">错误</TableCell>
                    <TableCell align="right">429</TableCell>
                    <TableCell align="right">prompt</TableCell>
                    <TableCell align="right">completion</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {data.map((u, i) => (
                    <TableRow key={`${u.bucket}-${u.dimension_value}-${i}`}>
                      <TableCell><Mono sx={{ fontSize: 12.5 }}>{u.bucket}</Mono></TableCell>
                      <TableCell><Mono sx={{ fontSize: 12.5 }}>{u.dimension_value}</Mono></TableCell>
                      <TableCell align="right"><Mono sx={{ fontSize: 12.5 }}>{u.requests}</Mono></TableCell>
                      <TableCell align="right"><Mono sx={{ fontSize: 12.5, color: u.errors ? "error.main" : "text.secondary" }}>{u.errors}</Mono></TableCell>
                      <TableCell align="right"><Mono sx={{ fontSize: 12.5, color: u.rate_limited ? "warning.main" : "text.secondary" }}>{u.rate_limited}</Mono></TableCell>
                      <TableCell align="right"><Mono sx={{ fontSize: 12.5, color: "text.secondary" }}>{u.prompt_tokens}</Mono></TableCell>
                      <TableCell align="right"><Mono sx={{ fontSize: 12.5, color: "text.secondary" }}>{u.completion_tokens}</Mono></TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </>
        )}
      </Panel>
    </Box>
  );
}
