## Biomarker extraction
### Prerequisites
We use the open-source software *Voreen* for graph and feature extraction from a segmentation map. Please install the tool from [this source](https://github.com/jqmcginnis/voreen_tools).

### Usage
Move all segmentation .png files that you wish to analyse into a seperate folder.

```sh
# Extract node and edge features into csv files and save graph as image
python graph_feature_extractor.py --image_dir [PATH_TO_FOLDER] --voreen_tool_path [PATH_TO_BIN_FOLDER] --graph_image true
```