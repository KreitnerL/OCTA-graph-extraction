> [!WARNING]
> This repository is work in progress
# OCTA GRAPH FEATURE ANALYSIS

This repository enables the quantitative analysis of OCTA images. Given a vessel segmentation map, we provide code for FAZ segmentation and graph feature extraction. We use the open-source software [*Voreen*](https://www.uni-muenster.de/Voreen/) for graph and feature extraction. See [https://github.com/TUM-AIMED/OCTA-seg](https://github.com/KreitnerL/OCTA-seg) to obtain detailed vessel segmentations for your OCTA images.
<div style="text-align:center">
    <img src="images/graph_extraction_pipeline.png" style="max-width:1000px">
</div>

# 🔴 TL;DR: Get graph features from my segmentations
For convenience, we provide a docker file to perform feature extraction:
```sh
# Build Docker image. (This can take a while. Only required once.)
docker build . -t octa-graph-extraction
``` 

To extract features from the ETDRS grid with FAZ segmentation replace the placeholders with your directory paths and run:
```sh
docker run -v [DATASET_DIR]:/var/segmentations -v [FAZ_SAVE_DIR]:/var/faz -v [RESULT_DIR]:/var/results octa-graph-extraction etdrs_pipeline
``` 
> [!NOTE]
> Voreen works best on 3D segmentations. We recommend to use our [3D reconstruction tool](https://github.com/TUM-AIMED/OCTA-seg#3-generate-a-3d-reconstruction-of-your-2d-segmentation-map-results-will-be-given-as-nifti-file) to convert 2D segmentation masks to a 3D nifti file.

# Notebook examples
Check out our two jupyter notebooks where we provide a detailed example for ETDRS analysis of a dataset with all steps. You can choose between:
- [docker_example_ETDRS_analysis.ipynb](./docker_example_ETDRS_analysis.ipynb) (Only uses the docker image)
- [manual_example_ETDRS_analysis.ipynb](./manual_example_ETDRS_analysis.ipynb) (Uses the python files)

# List of all docker features
- ROI Cropping: 
    ```sh
    docker run -v [DATASET_DIR]:/var/images -v [OUTPUT_DIR]:/var/results octa-graph-extraction roi
    ```
- FAZ segmentation from 2D segmentation masks:
    ```sh
    docker run -v [SEGMENTATIONS_DIR]:/var/segmentations -v [OUTPUT_DIR]:/var/faz octa-graph-extraction faz_seg [--threads THREADS] [--num_samples NUM_SAMPLES]
    ```
- Graph feature extraction of full 2D segmentation mask or 3D segmentation volume using Voreen:
    ```sh
    docker run -v [SEGMENTATIONS_DIR]:/var/segmentations -v [OUTPUT_DIR]:/var/results octa-graph-extraction graph_extraction_full [--bulge_size BULGE_SIZE] [--no_graph_image] [--no_colorize_graph] [--thresholds THRESHOLDS] [--generate_graph_file] [--threads THREADS] [--verbose]
    ```
- Graph feature extraction using ETDRS grid of 2D segmentation mask or 3D segmentation volume using Voreen:
    ```sh
    docker run -v [SEGMENTATIONS_DIR]:/var/segmentations -v [FAZ_SEG_DIR]:/var/faz -v [OUTPUT_DIR]:/var/results octa-graph-extraction graph_extraction_etdrs [--bulge_size BULGE_SIZE] [--no_graph_image] [--no_colorize_graph] [--thresholds THRESHOLDS] [--generate_graph_file] [--threads THREADS] [--verbose]
    ```
- FAZ segmentation and graph feature extraction using ETDRS grid of 2D segmentation mask or 3D segmentation volume using Voreen:
    ```sh
    docker run -v [SEGMENTATIONS_DIR]:/var/segmentations -v [OUTPUT_DIR]:/var/results octa-graph-extraction etdrs_pipeline [--bulge_size BULGE_SIZE] [--no_graph_image] [--no_colorize_graph] [--thresholds THRESHOLDS] [--generate_graph_file] [--threads THREADS] [--verbose]
    ```
- Generate analysis summary file of dataset
    ```sh
    docker run -v [GRAPH_FEATURES_DIR]:/var/graph_files -v [OUTPUT_DIR]:/var/results [-v [FAZ_DIR]:/var/faz] octa-graph-extraction analysis [--radius_thresholds THRESHOLDS] [--from_3d] [--mm HEIGHT_IN_MM] [--radius_correction_factor FACTOR] [--etdrs] [--center_radius ETDRS_CENTER_RADIUS_IN_MM] [--inner_radius ETDRS_INNER_RADIUS_IN_MM]
    ```

# 🔵 Manual Installation
## Prerequisites
- Python: Install python from [the official website](https://www.python.org/downloads/). The code was tested with python version 3.10.
- Python requirements: Install the necessary python packages with:
    ```sh
    pip install -r requirements.txt
    ```
- Voreen: We use the open-source software *Voreen* for graph and feature extraction from a segmentation map. Please install the tool from [this source](https://github.com/jqmcginnis/voreen_tools). You might also want to check the provided [Dockerfile](Dockerfile) to simplify the installation.


## Usage
Move all segmentation .png files that you wish to analyse into a seperate folder.

### FAZ segmentation:
```sh
# Computes the FAZ segmentation mask
python faz_segmentation.py --source_dir [PATH_TO_SRC_FOLDER] --source_files "/*.png" --output_dir [PATH_TO_RESULT_FOLDER]
```
### Graph and feature extraction:
```sh
# Extract node and edge features into csv files and save graph as image
python graph_feature_extractor.py --image_dir [PATH_TO_SRC_FOLDER] --output_dir [PATH_TO_RESULT_FOLDER] --voreen_tool_path [PATH_TO_BIN_FOLDER] --colorize_graph True
```
### ETDRS grid analysis:
Collect the vessel segmentation maps and the matching faz segmentation files in two seperate folders. Note that the faz should always be computed on the entire image or the DVC image. If the image belongs to the left eye and contains an `"_OS_"` identifier, we define the left quadrant to be nasal. Otherwise the right quadrant is defined as nasal. The center of the ETDRS grid is set to the center of the FAZ.
<div style="text-align:center">
    <img src="images/etdrs.png" style="max-width:900px">
</div>

Create the analysis by running:

```sh
# Extract node and edge features into csv files and save graph as image
python graph_feature_extractor.py --image_dir [PATH_TO_SRC_FOLDER] --output_dir [PATH_TO_RESULT_FOLDER] --voreen_tool_path [PATH_TO_BIN_FOLDER] --colorize_graph True --ETDRS --faz_dir [PATH_TO_FAZ_DIR]
```

### Performance
To increase the speed of the analysis our tool uses multi-threading. Use `--threads [NUM_OF_THREADS]` to run the analysis with `[NUM_OF_THREADS]` concurrent threads. By default, all available cpus are utilized.

## Troubleshooting
If you encounter OUT_OF_MEMORY errors during the build process, you can set the number of processes for `make` to 1. Note that this will significantly increase the build runtime!
```sh
docker build . -t octa-graph-extraction --build-arg NUMBER_OF_PROCESSES=1
```