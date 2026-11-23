# One-shot: forward Windows loopback 8976 to the WSL NAT IP (admin required).
# Log goes to D:\Project\nim-proxy\spikes\cf-workers\scripts\portproxy.log
$log = "D:\Project\nim-proxy\spikes\cf-workers\scripts\portproxy.log"
"=== run at $(Get-Date) ===" | Out-File $log -Encoding utf8

$ip = & wsl.exe -d Ubuntu-24.04 -- hostname -I 2>$null
$ip = ($ip -split "\s+")[0]
"WSL IP: $ip" | Out-File $log -Append -Encoding utf8
if (-not $ip -match '^\d+\.\d+\.\d+\.\d+$') {
    "ERROR: could not read WSL IP" | Out-File $log -Append -Encoding utf8
    exit 1
}

$v4 = netsh interface portproxy add v4tov4 listenaddress=127.0.0.1 listenport=8976 connectaddress=$ip connectport=8976 2>&1
$v6 = netsh interface portproxy add v6tov4 listenaddress=::1 listenport=8976 connectaddress=127.0.0.1 connectport=8976 2>&1
"v4: $v4" | Out-File $log -Append -Encoding utf8
"v6: $v6" | Out-File $log -Append -Encoding utf8
netsh interface portproxy show all | Out-File $log -Append -Encoding utf8
"DONE" | Out-File $log -Append -Encoding utf8
