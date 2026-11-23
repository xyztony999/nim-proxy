import { Card, CardContent, List, ListItem, ListItemText, Typography } from "@mui/material";
import { getConfig } from "../api/actions";
import { ErrorPanel, Loading } from "../components/Feedback";
import { useApi } from "../hooks/useApi";

export default function Config() {
  const { data, loading, error } = useApi(getConfig);
  if (loading) return <Loading />;
  if (error) return <ErrorPanel message={error} />;
  if (!data) return null;
  const rows: [string, string | number][] = [
    ["上游地址", data.upstream],
    ["连接超时（秒）", data.connect_timeout],
    ["读超时（秒）", data.read_timeout],
    ["鉴权模式", data.auth_mode === "enforced" ? "强制鉴权" : "纯透传"],
    ["端口", data.port],
    ["存储后端", data.db_backend === "d1" ? "Cloudflare D1" : "SQLite"],
  ];
  return (
    <Card>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          运行配置（只读，来自环境变量）
        </Typography>
        <List>
          {rows.map(([k, v]) => (
            <ListItem key={k} divider>
              <ListItemText primary={k} secondary={String(v)} />
            </ListItem>
          ))}
        </List>
      </CardContent>
    </Card>
  );
}
