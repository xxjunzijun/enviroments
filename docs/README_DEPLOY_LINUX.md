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
- PyInstaller runs inside manylinux_2_34 containers, so the Linux package targets glibc 2.34. x64 uses `quay.io/pypa/manylinux_2_34_x86_64`; arm64 uses `quay.io/pypa/manylinux_2_34_aarch64`. Systems older than glibc 2.34 may still require a custom build on an older base.
- No Node.js, pnpm, Python, or pip is required on the offline machine.
- The runtime directory must be writable because SQLite data and logs are generated at runtime.
- SSH, SFTP, and Web SSH require network access from this machine to managed servers.

