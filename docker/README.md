## Architecture
- **Python Container**: Runs the main processing code with Docker CLI access
- **Voreen Container**: Used for vessel graph extraction
- **Automatic Configuration**: User/group IDs detected automatically for proper file permissions

## Path Configuration

The system automatically maps these directories (configurable in `.env`):
- **Input**: `${HOST_SRC_DIR}` → Container `/data/src`
- **Output**: `${HOST_OUTPUT_DIR}` → Container `/data/output`  
- **Temp**: `${HOST_TMP_DIR}` → Container `/tmp/voreen`

## Docker Communication & Volume Strategy

The DooD setup uses intelligent volume mounting:

```yaml
# Python container volumes
volumes:
  - /var/run/docker.sock:/var/run/docker.sock  # Docker socket for DooD
  - ${HOST_TMP_DIR}:/tmp/voreen                # Shared temp directory
  - ${HOST_SRC_DIR}:/data/src:ro              # Source data (read-only)
  - ${HOST_OUTPUT_DIR}:/data/output           # Output directory

# Voreen container volumes (created dynamically)
volumes:
  - ${HOST_TMP_DIR}:/var/tmp                  # Shared temp directory
  - ${HOST_SRC_DIR}:/var/src:ro              # Source data (read-only)
  - ${HOST_OUTPUT_DIR}:/var/results          # Output directory
```

## How It Works

1. **Path Mapping**: Host paths are mounted to both containers:
   - **Host** → **Python Container** → **Voreen Container**
   - `/your/data` → `/data/src` → `/var/src`
   - `/your/output` → `/data/output` → `/var/results`

2. **Docker Communication**: Python container has Docker socket access and dynamically creates/manages Voreen containers

3. **Automatic Adaptation**: System detects and configures user IDs, Docker group, and paths automatically