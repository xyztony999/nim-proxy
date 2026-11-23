import { Box, Divider, Typography } from "@mui/material";
import { getConfig } from "../api/actions";
import { ErrorPanel, Loading } from "../components/Feedback";
import { Mono, PageHeader, Panel } from "../components/ui";
import { useApi } from "../hooks/useApi";

export default function Config() {
  const { data, loading, error } = useApi(getConfig);
  if (loading) return <Loading />;
  if (error) return <ErrorPanel message={error} />;
  if (!data) return null;

  const rows: [string, string, string?][] = [
    ["上游地址", data.upstream],
    ["连接超时", `${data.connect_timeout} 秒`],
    ["读超时", `${data.read_timeout} 秒`],
    ["鉴权模式", data.auth_mode === "enforced" ? "强制鉴权" : "纯透传", data.auth_mode === "enforced" ? "success.main" : "warning.main"],
    ["监听端口", String(data.port)],
    ["存储后端", data.db_backend === "d1" ? "Cloudflare D1" : "SQLite"],
  ];

  return (
    <Box>
      <PageHeader title="运行配置" subtitle="只读，来自环境变量；修改后需重启服务" />
      <Panel sx={{ maxWidth: 640 }}>
        {rows.map(([label, value, color], i) => (
          <Box key={label}>
            {i > 0 && <Divider />}
            <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 2, px: 2.5, py: 1.75 }}>
              <Typography variant="body2" color="text.secondary">{label}</Typography>
              <Mono sx={{ fontSize: 13, color: color ?? "text.primary" }}>{value}</Mono>
            </Box>
          </Box>
        ))}
      </Panel>
    </Box>
  );
}
