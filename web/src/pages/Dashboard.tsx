import { Box, Grid, Typography } from "@mui/material";
import { getDashboard } from "../api/actions";
import { ErrorPanel, Loading } from "../components/Feedback";
import { Mono, PageHeader, Panel, RelayPipeline, StatTile } from "../components/ui";
import { useApi } from "../hooks/useApi";

export default function Dashboard() {
  const { data, loading, error } = useApi(getDashboard);
  if (loading) return <Loading />;
  if (error) return <ErrorPanel message={error} />;
  if (!data) return null;

  return (
    <Box>
      <PageHeader title="运行看板" subtitle="NVIDIA NIM 中继的实时状态与今日用量" />

      <Panel sx={{ p: 3, mb: 3 }}>
        <Grid container spacing={3} alignItems="center">
          <Grid size={{ xs: 12, md: 7 }}>
            <RelayPipeline live={data.status === "ok"} />
          </Grid>
          <Grid size={{ xs: 12, md: 5 }}>
            <Box sx={{ display: "flex", flexDirection: "column", gap: 1.5 }}>
              <Box sx={{ display: "flex", justifyContent: "space-between", gap: 2 }}>
                <Typography variant="body2" color="text.secondary">上游地址</Typography>
                <Mono sx={{ fontSize: 13 }}>{data.upstream.replace("https://", "")}</Mono>
              </Box>
              <Box sx={{ display: "flex", justifyContent: "space-between", gap: 2 }}>
                <Typography variant="body2" color="text.secondary">鉴权模式</Typography>
                <Mono sx={{ fontSize: 13, color: data.auth_mode === "enforced" ? "success.main" : "warning.main" }}>
                  {data.auth_mode === "enforced" ? "强制鉴权" : "纯透传"}
                </Mono>
              </Box>
              <Box sx={{ display: "flex", justifyContent: "space-between", gap: 2 }}>
                <Typography variant="body2" color="text.secondary">服务状态</Typography>
                <Mono sx={{ fontSize: 13, color: "success.main" }}>{data.status}</Mono>
              </Box>
            </Box>
          </Grid>
        </Grid>
      </Panel>

      <Grid container spacing={2}>
        <Grid size={{ xs: 6, md: 4, lg: 2.4 }}>
          <StatTile label="今日请求" value={data.today.requests} accent="secondary.main" />
        </Grid>
        <Grid size={{ xs: 6, md: 4, lg: 2.4 }}>
          <StatTile label="今日错误" value={data.today.errors} accent="error.main" />
        </Grid>
        <Grid size={{ xs: 6, md: 4, lg: 2.4 }}>
          <StatTile label="今日 429" value={data.today.rate_limited} accent="warning.main" />
        </Grid>
        <Grid size={{ xs: 6, md: 6, lg: 2.4 }}>
          <StatTile label="上游密钥" value={data.upstream_key_count} accent="success.main" />
        </Grid>
        <Grid size={{ xs: 6, md: 6, lg: 2.4 }}>
          <StatTile label="客户端密钥" value={data.client_key_count} accent="success.main" />
        </Grid>
      </Grid>
    </Box>
  );
}
