import { Card, CardContent, Grid, Typography } from "@mui/material";
import { getDashboard } from "../api/actions";
import { ErrorPanel, Loading } from "../components/Feedback";
import { useApi } from "../hooks/useApi";

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <Card>
      <CardContent>
        <Typography variant="body2" color="text.secondary">
          {label}
        </Typography>
        <Typography variant="h5">{value}</Typography>
      </CardContent>
    </Card>
  );
}

export default function Dashboard() {
  const { data, loading, error } = useApi(getDashboard);
  if (loading) return <Loading />;
  if (error) return <ErrorPanel message={error} />;
  if (!data) return null;
  return (
    <Grid container spacing={2}>
      <Grid size={{ xs: 12, sm: 6, md: 3 }}>
        <Stat label="服务状态" value={data.status} />
      </Grid>
      <Grid size={{ xs: 12, sm: 6, md: 3 }}>
        <Stat label="鉴权模式" value={data.auth_mode === "enforced" ? "强制鉴权" : "纯透传"} />
      </Grid>
      <Grid size={{ xs: 12, sm: 6, md: 3 }}>
        <Stat label="上游密钥" value={data.upstream_key_count} />
      </Grid>
      <Grid size={{ xs: 12, sm: 6, md: 3 }}>
        <Stat label="客户端密钥" value={data.client_key_count} />
      </Grid>
      <Grid size={{ xs: 12, sm: 4 }}>
        <Stat label="今日请求" value={data.today.requests} />
      </Grid>
      <Grid size={{ xs: 12, sm: 4 }}>
        <Stat label="今日错误" value={data.today.errors} />
      </Grid>
      <Grid size={{ xs: 12, sm: 4 }}>
        <Stat label="今日 429" value={data.today.rate_limited} />
      </Grid>
      <Grid size={{ xs: 12 }}>
        <Card>
          <CardContent>
            <Typography variant="body2" color="text.secondary">
              上游地址
            </Typography>
            <Typography>{data.upstream}</Typography>
          </CardContent>
        </Card>
      </Grid>
    </Grid>
  );
}
