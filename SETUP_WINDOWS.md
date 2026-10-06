# Windows 10/11 setup

OpenNet's engine uses Linux/POSIX sockets. **Do not run the Linux build from ordinary CMD or PowerShell.** Use WSL2 or Docker Desktop.

## Option A — WSL2 Ubuntu (recommended for learning C++)

1. Extract `OpenNet-Source.zip`. The working folder is the inner `opennet` folder containing `README.md`, `Makefile` and `CMakeLists.txt`.
2. If WSL is not installed, open **PowerShell as Administrator** and run:

   ```powershell
   wsl --install -d Ubuntu
   ```

   Restart Windows if requested. Open Ubuntu and create its Linux username/password.
3. In the **Ubuntu terminal**, navigate to your extracted folder. For example, Windows `F:\projects\opennet` is `/mnt/f/projects/opennet`:

   ```bash
   cd /mnt/f/projects/opennet
   ```

   Substitute your actual location. You can instead copy the project into `~/projects/opennet` for faster Linux filesystem builds. Do not use a Windows path such as `F:\...` directly inside Bash.
4. Install the compiler and dependencies:

   ```bash
   sudo apt update
   sudo apt install -y build-essential cmake libssl-dev python3
   ```

5. Set up and verify:

   ```bash
   bash scripts/setup.sh
   make test
   make demo
   ```

6. Open **http://localhost:3000** in your Windows browser. Leave the Ubuntu terminal open.
7. Open a second Ubuntu terminal in the same folder:

   ```bash
   ./opennet ping server.local
   ./opennet curl http://server.local/
   ./opennet fault kill router-2
   ```

   Wait about four seconds, then `./opennet traceroute server.local`. Restore the router with `./opennet fault restart router-2`.
8. Press **Ctrl+C** in the first terminal to stop. Later launches only need `./opennet start`.

If executable permissions were lost during extraction, run `chmod +x opennet scripts/*.sh`, or use `python3 opennet ...` / `bash scripts/start_demo.sh`.

## Option B — Docker Desktop

Install and start Docker Desktop with its WSL2 backend and Linux containers. Open PowerShell in the extracted `opennet` folder:

```powershell
docker compose up --build
```

Or double-click `START_DOCKER_WINDOWS.bat`. Initial setup downloads the Ubuntu image and dependencies. Open **http://localhost:3000** after the startup message.

From a second PowerShell window:

```powershell
docker compose exec opennet python3 opennet ping server.local
docker compose exec opennet python3 opennet fault kill router-2
docker compose exec opennet python3 opennet traceroute server.local
```

Stop with Ctrl+C, then `docker compose down`.

## Common mistakes

- No `npm install`, `pip install`, Python virtual environment or Visual Studio project is needed.
- Native Windows Python cannot run this controller because process locking uses `fcntl`; run it inside WSL2/Docker.
- Use the folder containing `CMakeLists.txt`, not the ZIP or its outer download folder.
- Port 3000 must be free. On WSL, choose `./opennet start --port 3001` if needed, then browse that port. Docker host/internal ports should match because of the Host validation check.
- The Windows / Docker flows are documented and included but were not executed during package validation. The engine and controller were tested on Linux.
