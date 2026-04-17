# Linux Offline Deployment

This package is built by GitHub Actions on Linux arm64. It contains the backend executable and bundled frontend static files.

## Run

```bash
tar -xzf Enviroments-linux-arm64-*.tar.gz
cd Enviroments-linux-arm64-*
chmod +x Enviroments
./Enviroments
```

The service listens on `0.0.0.0:8000` by default. Open:

```text
http://<server-ip>:8000
```

## Notes

- Use this package on Linux ARM64.
- PyInstaller runs inside `quay.io/pypa/manylinux_2_34_aarch64`, so the Linux ARM64 package targets glibc 2.34. Systems older than glibc 2.34 may still require a custom build on an older base.
- No Node.js, pnpm, Python, or pip is required on the offline machine.
- The runtime directory must be writable because SQLite data and logs are generated at runtime.
- SSH, SFTP, and Web SSH require network access from this machine to managed servers.

