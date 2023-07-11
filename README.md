> ⚠️ **_NOTE:_** This repository is work in progress
# OCTA GRAPH FEATURE ANALYSIS

This repository enables the quantitative analysis of OCTA images. Given a vessel segmentation map, we provide code for FAZ segmentation and graph feature extraction. We use the open-source software *Voreen* for graph and feature extraction. See [https://github.com/TUM-AIMED/OCTA-seg](https://github.com/KreitnerL/OCTA-seg) to obtain detailed vessel segmentations for your OCTA images.
<div style="text-align:center">
    <img src="images/graph_extraction_pipeline.png">
</div>

# 🔴 TL;DR: Get graph features from my segmentations
For convenience, we provide a docker file to perform feature extraction:
```sh
# Build Docker image. (This can take a while. Only required once.)
docker build . -t octa-graph-extraction
``` 
To extract features from the **entire** image replace the placeholders with your directory paths and run:
```sh
docker run -v [DATASET_DIR]:/var/segmentations -v [RESULT_DIR]:/var/results octa-graph-extraction normal
``` 

<!-- docker run -v /home/linus/repos/OCTA-graph-extraction/test1:/var/segmentations -v /home/linus/repos/OCTA-graph-extraction/test2:/var/segmentation octa-graph-extraction NORMAL -->
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
    <img src="images/etdrs.png">
</div>

Create the analysis by running:

```sh
# Extract node and edge features into csv files and save graph as image
python graph_feature_extractor.py --image_dir [PATH_TO_SRC_FOLDER] --output_dir [PATH_TO_RESULT_FOLDER] --voreen_tool_path [PATH_TO_BIN_FOLDER] --colorize_graph True --ETDRS --faz_dir [PATH_TO_FAZ_DIR]
```

### Performance
To increase the speed of the analysis you can use multi-threading. Use `--threads [NUM_OF_THREADS]` to run the analysis with `[NUM_OF_THREADS]` concurrent threads.