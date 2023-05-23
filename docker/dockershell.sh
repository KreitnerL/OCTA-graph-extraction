#!/bin/bash
echo "[Info] Mode: $1"

if [ "$1" = "normal" ]
then 
    python /home/OCTA-graph-extraction/graph_feature_extractor.py --image_dir /var/segmentations --output_dir /var/results --bulge_size 3 --voreen_tool_path /home/software/voreen-src-unix-nightly/bin/ --colorize_graph True
elif [ "$1" = "ETDRS" ]
then
    echo "Mode ETDRS is not yet implemented."
    exit 1
    # TODO
    # python /home/OCTA-graph-extraction/graph_feature_extractor.py --image_dir /var/segmentations --output_dir /var/results --bulge_size 3 --voreen_tool_path /home/software/voreen-src-unix-nightly/bin/ --colorize_graph True
else
    echo "Mode $1 does not exist. Choose segmentation or generation."
    exit 1
fi