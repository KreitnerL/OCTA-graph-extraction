# Biomarker extraction
We use the open-source software *Voreen* for graph and feature extraction from a segmentation map. TODO

# 🔴 TL;DR: Get graph features from my segmentations
For convenience, we provide a docker file to perform feature extraction:
```sh
# Build Docker image. (Only required once)
docker build . -t octa-graph-extraction
``` 
To extract features from the **entire** image replace the placeholders with your directory paths and run:
```sh
docker run -v [DATASET_DIR]:/var/segmentations -v [RESULT_DIR]:/var/results octa-graph-extraction normal
``` 

<!-- docker run -v /home/linus/repos/OCTA-graph-extraction/test1:/var/segmentations -v /home/linus/repos/OCTA-graph-extraction/test2:/var/segmentation octa-graph-extraction NORMAL -->

### Prerequisites
We use the open-source software *Voreen* for graph and feature extraction from a segmentation map. Please install the tool from [this source](https://github.com/jqmcginnis/voreen_tools).

### Usage
Move all segmentation .png files that you wish to analyse into a seperate folder.

```sh
# Extract node and edge features into csv files and save graph as image
python graph_feature_extractor.py --image_dir [PATH_TO_FOLDER] --voreen_tool_path [PATH_TO_BIN_FOLDER] --graph_image true
```