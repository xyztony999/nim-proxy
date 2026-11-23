import {
  FormControl, InputLabel, MenuItem, Paper, Select, Table, TableBody, TableCell,
  TableHead, TableRow, Typography,
} from "@mui/material";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useState } from "react";
import { getUsage } from "../api/actions";
import { ErrorPanel, Loading } from "../components/Feedback";
import { useApi } from "../hooks/useApi";

export default function Usage() {
  const [dimension, setDimension] = useState("key");
  const [bucket, setBucket] = useState("day");
  const { data, loading, error } = useApi(
    () => getUsage({ dimension_type: dimension, bucket_type: bucket }),
    [dimension, bucket],
  );

  return (
    <Paper sx={{ p: 2 }}>
      <Typography variant="h6" gutterBottom>
        用量统计
      </Typography>
      <FormControl size="small" sx={{ mr: 2, minWidth: 140 }}>
        <InputLabel>维度</InputLabel>
        <Select value={dimension} label="维度" onChange={(e) => setDimension(e.target.value)}>
          <MenuItem value="key">按密钥</MenuItem>
          <MenuItem value="model">按模型</MenuItem>
          <MenuItem value="status">按状态码</MenuItem>
        </Select>
      </FormControl>
      <FormControl size="small" sx={{ minWidth: 120 }}>
        <InputLabel>粒度</InputLabel>
        <Select value={bucket} label="粒度" onChange={(e) => setBucket(e.target.value)}>
          <MenuItem value="hour">小时</MenuItem>
          <MenuItem value="day">天</MenuItem>
        </Select>
      </FormControl>

      {loading && <Loading />}
      {error && <ErrorPanel message={error} />}
      {data && (
        <>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={data} margin={{ top: 16, right: 16, bottom: 0, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="dimension_value" />
              <YAxis allowDecimals={false} />
              <Tooltip />
              <Legend />
              <Bar dataKey="requests" name="请求" fill="#3b6fd4" />
              <Bar dataKey="errors" name="错误" fill="#d32f2f" />
              <Bar dataKey="rate_limited" name="429" fill="#ed6c02" />
            </BarChart>
          </ResponsiveContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>时段</TableCell>
                <TableCell>维度值</TableCell>
                <TableCell align="right">请求</TableCell>
                <TableCell align="right">错误</TableCell>
                <TableCell align="right">429</TableCell>
                <TableCell align="right">prompt tokens</TableCell>
                <TableCell align="right">completion tokens</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {data.map((u, i) => (
                <TableRow key={`${u.bucket}-${u.dimension_value}-${i}`}>
                  <TableCell>{u.bucket}</TableCell>
                  <TableCell>{u.dimension_value}</TableCell>
                  <TableCell align="right">{u.requests}</TableCell>
                  <TableCell align="right">{u.errors}</TableCell>
                  <TableCell align="right">{u.rate_limited}</TableCell>
                  <TableCell align="right">{u.prompt_tokens}</TableCell>
                  <TableCell align="right">{u.completion_tokens}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </>
      )}
    </Paper>
  );
}
