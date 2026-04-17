# Linux Offline Deployment

This package is built by GitHub Actions on Linux x64 or Linux arm64. It contains the backend executable and bundled frontend static files.

## Run

```bash
tar -xzf Enviroments-linux-*.tar.gz
cd Enviroments-linux-*
chmod +x Enviroments
./Enviroments
```

The service listens on `0.0.0.0:8000` by default. Open:

```text
http://<server-ip>:8000
```

## Notes

- Use the x64 package on Linux x86_64 and the arm64 package on Linux ARM64.
- Build on GitHub uses Ubuntu 22.04 for x64 and ubuntu-22.04-arm for arm64. Very old offline systems may fail because of glibc compatibility. If that happens, build on a Linux version closer to the target environment.
- No Node.js, pnpm, Python, or pip is required on the offline machine.
- The runtime directory must be writable because SQLite data and logs are generated at runtime.
- SSH, SFTP, and Web SSH require network access from this machine to managed servers.

