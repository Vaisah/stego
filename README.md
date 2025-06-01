# StegoApp Docker & WSL Setup Guide

This guide walks you through configuring Docker with Windows Subsystem for Linux (WSL) to build and run the StegoApp (steganography analysis) in a reproducible, cross‑platform environment.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Enable WSL 2](#enable-wsl-2)
3. [Install Docker Desktop](#install-docker-desktop)
4. [Configure Docker for WSL](#configure-docker-for-wsl)
5. [Clone StegoApp Repository](#clone-stegoapp-repository)
6. [Build the Docker Image](#build-the-docker-image)
7. [Run the Container](#run-the-container)
8. [Volume Mounts & Persistence](#volume-mounts--persistence)
9. [Development Workflow](#development-workflow)
10. [Troubleshooting](#troubleshooting)

---

## Prerequisites

- **Windows 10/11 (2004+)** with WSL 2 support
- **Windows Subsystem for Linux (WSL)** installed
- **Docker Desktop** for Windows
- Basic familiarity with command line (PowerShell / Windows Terminal)

---

## 1. Enable WSL 2

1. Open PowerShell as Administrator and run:

   ```powershell
   wsl --install
   ```

2. Reboot your machine when prompted.
3. Verify WSL version:

   ```powershell
   wsl --list --verbose
   ```

   Ensure your default distro shows `Version 2`.

---

## 2. Install Docker Desktop

1. Download the latest Docker Desktop for Windows from [docker.com](https://www.docker.com).
2. Run the installer and check **"Use WSL 2 instead of Hyper-V"** on the configuration screen.
3. Complete the installation and launch Docker Desktop.

---

## 3. Configure Docker for WSL

1. Open **Docker Desktop** Settings → **Resources** → **WSL Integration**.
2. Toggle **Enable integration with my default WSL distro**.
3. Optionally enable integration with additional distros (e.g., `ubuntu-20.04`).

---

## 4. Clone StegoApp Repository

In your WSL terminal (e.g., Ubuntu):

```bash
git clone https://github.com/yourusername/stegoapp.git
cd stegoapp
```

---

## 5. Build the Docker Image

From within the `stegoapp/` directory:

```bash
docker build -t stegoapp:latest -f Dockerfile .
```

This will:

- Install dependencies (Python, steg-tools)
- Copy application code
- Expose the API on port `5000`

---

## Docker Compose

1. Create a `docker-compose.yml` at the project root:

   ```yaml
   version: "3.8"

   services:
     stegoapp:
       build:
         context: .
         dockerfile: Dockerfile
       image: stegoapp:latest
       ports:
         - "5000:5000"
       volumes:
         - ./data:/app/data
       environment:
         - ENV=development
   ```

2. Build and start the service:

   ```bash
   docker-compose up --build
   ```

3. To stop and remove containers:

   ```bash
   docker-compose down
   ```

## 6. Run the Container

```bash
docker run --rm -it \
  -p 5000:5000 \
  -v $(pwd)/data:/app/data \
  stegoapp:latest
```

- **`-p 5000:5000`** maps the API port to localhost
- **`-v $(pwd)/data:/app/data`** persists scans and results

Visit **[http://localhost:5000](http://localhost:5000)** in your browser or use `curl`:

```bash
curl http://localhost:5000/health
```

---

## 7. Volume Mounts & Persistence

- **`./data/`** stores uploaded images, scan outputs, and logs
- To reset state, simply delete `./data/`

---

## 8. Development Workflow

1. **Code changes**: edit files in your WSL project folder.
2. **Rebuild**: `docker build --no-cache -t stegoapp:dev -f Dockerfile .`
3. **Run**: mount current code into container:

   ```bash

   ```

docker run --rm -it&#x20;
-p 5000:5000&#x20;
-v \$(pwd)/stego_core:/app/stego_core&#x20;
-v \$(pwd)/data:/app/data&#x20;
stegoapp\:dev

```
4. **Test**: use Postman or automated test suite inside container.

---

## 9. Troubleshooting

- **WSL Distro Not Visible**: ensure your distro is set to version 2 (`wsl --set-version <distro> 2`).
- **Permission Errors**: run `sudo chown -R $(id -u):$(id -g) data/` inside WSL.
- **Docker Daemon Not Running**: confirm Docker Desktop is running and restart if necessary.

---

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

---

*Guide updated: June 2025*

```
