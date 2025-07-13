# OCTA GRAPH FEATURE ANALYSIS

This repository enables the quantitative analysis of OCTA images. Given a vessel segmentation map, we provide FAZ segmentation and graph feature extraction. We use the open-source software [*Voreen*](https://www.uni-muenster.de/Voreen/) for graph and feature extraction. See [https://github.com/aiforvision/OCTA-autosegmentation](https://github.com/aiforvision/OCTA-autosegmentation) to obtain detailed vessel segmentations for your OCTA images.

<div style="text-align:center">
    <img src="images/graph_extraction_pipeline.png" style="max-width:1000px">
</div>

# 📄 How to Cite

If you use this software in your research, please cite:

```bibtex
@misc{octa-graph-extraction,
  title={OCTA Graph Feature Analysis V1},
  author={Linus Kreitner, Laurin Lux, Daniel Rueckert, Martin Menten},
  year={2025},
  url={https://github.com/KreitnerL/OCTA-graph-extraction},
  note={Software for quantitative analysis of OCTA images with FAZ segmentation and graph feature extraction}
}
```

# Table of Contents
- [OCTA GRAPH FEATURE ANALYSIS](#octa-graph-feature-analysis)
- [📄 How to Cite](#-how-to-cite)
- [Table of Contents](#table-of-contents)
- [🛠️ Installation \& Setup](#️-installation--setup)
    - [📦 Prerequisites](#-prerequisites)
- [🚀 Usage Examples](#-usage-examples)
  - [🐍+🐋 Host Python Setup Usage](#-host-python-setup-usage)
  - [🐋+🐋 Full Docker Setup Usage](#-full-docker-setup-usage)
  - [ETDRS Grid Analysis](#etdrs-grid-analysis)
- [Customizations (optional)](#customizations-optional)
  - [🐋 Manual Container Management](#-manual-container-management)
  - [📁 Path Configuration](#-path-configuration)
  - [⚡Multi-threading](#multi-threading)
- [🔍 Troubleshooting](#-troubleshooting)
  - [Setup Issues](#setup-issues)
    - [UV Installation (Host Python setup)](#uv-installation-host-python-setup)
    - [Build Issues](#build-issues)
    - [Permission Issues](#permission-issues)
  - [Runtime Issues](#runtime-issues)
    - [Path Problems](#path-problems)
    - [Container Issues (Full Docker setup)](#container-issues-full-docker-setup)
    - [Python Environment Issues (Host Python setup)](#python-environment-issues-host-python-setup)
  - [Debug Mode](#debug-mode)
    - [Verbose Output](#verbose-output)
    - [Manual Container Debugging (Full Docker)](#manual-container-debugging-full-docker)
- [📖 Additional Resources](#-additional-resources)
  - [Notebook Examples](#notebook-examples)

# 🛠️ Installation & Setup

### 📦 Prerequisites
- Docker installed on your host system
- Access to the Docker daemon (user should be in the `docker` group)

This project supports two workflows you can choose between:
1. **🐍+🐋 Host Python + Docker Voreen** (recommended for development)
2. **🐋+🐋 Full Docker Setup** (recommended for production/simple usage)

```bash
./setup.sh  # Interactive setup (one-time) - choose your workflow
```

# 🚀 Usage Examples

After running `./setup.sh`, you can use the automated command runners that handle container lifecycle and path configuration automatically.

## 🐍+🐋 Host Python Setup Usage

Make sure that you environment is activated: 
```sh
source .venv/bin/activate
```

**📋 Basic Commands:**
```bash
# FAZ segmentation
python faz_segmentation.py --source_files /path/to/images --output_dir /path/to/output

# Graph extraction
python graph_feature_extractor.py --image_files /path/to/segmentations --output_dir /path/to/results

# Analysis summary
python generate_analysis_summary.py --source_dir /path/to/graph_files --segmentation_dir /path/to/segmentations --output_dir /path/to/results [--radius_thresholds r1,...,rn]
```

## 🐋+🐋 Full Docker Setup Usage

Use the `run_analysis.sh` script for automated container management:

**📋 Basic Commands:**
```bash
# FAZ segmentation (auto-starts containers, runs command, cleans up)
./run_analysis.sh faz_seg --source_dir /path/to/images --output_dir /path/to/output

# Graph extraction with automatic container management
./run_analysis.sh graph --source_dir /path/to/segmentations --output_dir /path/to/results

# Generate analysis summary
./run_analysis.sh summary --source_dir /path/to/graph_files --output_dir /path/to/results [-- --radius_thresholds r1,...,rn]

# Complete pipeline (faz segmentation + graph extraction + summary)
./run_analysis.sh pipeline --source_dir /path/to/data --output_dir /path/to/results [--radius_thresholds r1,...,rn]

# Complete ETDRS pipeline (faz segmentation + ETDRS drid graph extraction + summary)
./run_analysis.sh etdrs_pipeline --source_dir /path/to/data --output_dir /path/to/results
```

**🔧 Further Options:**
```bash
# Pass additional arguments to the underlying commands
./run_analysis.sh graph --source_dir /data --output_dir /results -- --verbose --threads 8

# Use different temporary directory
./run_analysis.sh etdrs_pipeline --source_dir /data --output_dir /results --tmp_dir /custom/tmp

# Help and available commands
./run_analysis.sh --help
```

## ETDRS Grid Analysis
The ETDRS (Early Treatment Diabetic Retinopathy Study) grid analysis divides the retinal image into standardized regions for quantitative analysis. The center of the grid is automatically set to the center of the FAZ (Foveal Avascular Zone).

<div style="text-align:center">
    <img src="images/etdrs.png" style="max-width:900px">
</div>

You can use ETDRS analysis by adding the `--etdrs` flag for graph extraction and summary generation.


> [!NOTE]
> - FAZ should be computed on the entire image or DVC image
> - For left eye images with `"_OS_"` identifier: left quadrant = nasal, else right quadrant = nasal
> - Vessel and FAZ segmentation files should be in separate folders with matching names


# Customizations (optional)
## 🐋 Manual Container Management
```bash
# Start containers manually (if needed)
docker-compose up -d

# Run commands in running containers
docker-compose exec octa-graph-extraction /home/OCTA-graph-extraction/docker/dockershell.sh faz_seg --verbose

# Stop containers
docker-compose down
```
## 📁 Path Configuration

**Option 1: Command-line (recommended)**
```bash
# Specify paths directly when running commands
./run_analysis.sh faz_seg --source_dir /your/data --output_dir /your/results

# or for host Python
./run_host.sh faz_seg --source_dir /your/data --output_dir /your/results
```

**Option 2: Environment file**
```bash
# Edit .env file to set default paths
HOST_TMP_DIR=/tmp/voreen
HOST_SRC_DIR=/path/to/your/data
HOST_OUTPUT_DIR=/path/to/your/results
```

**Option 3: Environment variables**
```bash
# Set for current session
export HOST_SRC_DIR=/path/to/data
export HOST_OUTPUT_DIR=/path/to/results
./run_analysis.sh faz_seg  # Will use environment variables
```

## ⚡Multi-threading
Increase the number of concurrent threads for faster dataset processing or decrease for smaller memory footprint. By default, all available CPU cores are used:
```sh
# Full docker
./run_analysis.sh graph --source_dir /data --output_dir /results -- --threads 8 --verbose
# Python + Docker
python graph_feature_extractor.py --image_files /path/to/segmentations --output_dir /path/to/results --threads 8
```

# 🔍 Troubleshooting

## Setup Issues

### UV Installation (Host Python setup)
If UV installation fails:
```bash
# Manual UV installation
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc  # or restart terminal
```

### Build Issues
If you encounter OUT_OF_MEMORY errors during the build process:
```bash
# Edit .env file and reduce NUMBER_OF_PROCESSES
NUMBER_OF_PROCESSES=1
# Then re-run setup
./setup.sh
```

### Permission Issues
```bash
# Fix ownership of output directory
sudo chown -R $USER:$USER /path/to/output

# Ensure Docker socket access
sudo usermod -aG docker $USER
# Log out and log back in for group changes to take effect
```

## Runtime Issues

### Path Problems
The automated runners handle most path issues, but if you encounter problems:
```bash
# Check your paths are accessible
ls -la /path/to/your/source/data
ls -la /path/to/your/output/directory

# Use absolute paths
./run_analysis.sh faz_seg --source_dir /absolute/path/to/data --output_dir /absolute/path/to/output
```

### Container Issues (Full Docker setup)
```bash
# Check container status
docker-compose ps

# View logs
docker-compose logs octa-graph-extraction
docker-compose logs voreen

# Force cleanup and restart
docker-compose down --remove-orphans
./run_analysis.sh faz_seg --source_dir /your/data --output_dir /your/results
```

### Python Environment Issues (Host Python setup)
```bash
# Check virtual environment
source .venv/bin/activate
python -c "import docker; print('Docker SDK OK')"

# Reinstall dependencies if needed
uv sync

# Check Voreen container
docker run --rm voreen echo "Voreen test"
```

## Debug Mode

### Verbose Output
Add `--verbose` to see detailed processing information:
```bash
./run_analysis.sh faz_seg --source_dir /data --output_dir /results -- --verbose
```

### Manual Container Debugging (Full Docker)
```bash
# Start containers manually for debugging
docker-compose up -d

# Shell into containers
docker-compose exec octa-graph-extraction bash
docker-compose exec voreen bash

# Stop when done
docker-compose down
```


# 📖 Additional Resources

## Notebook Examples
Check out our jupyter notebooks for detailed ETDRS analysis examples:
- [docker_example_ETDRS_analysis.ipynb](./docker_example_ETDRS_analysis.ipynb) - Uses Docker setup
- [manual_example_ETDRS_analysis.ipynb](./manual_example_ETDRS_analysis.ipynb) - Uses Python files directly
