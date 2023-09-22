#!/bin/bash
echo "[Info] Mode: $1"
mode=$1
shift

if [ "$mode" = "faz_seg" ]
then
    python /home/OCTA-graph-extraction/faz_segmentation.py --source_dir /var/segmentations --source_files "/**/*.png" --output_dir /var/faz "$@"
elif [ "$mode" = "full" ]
then 
    python /home/OCTA-graph-extraction/graph_feature_extractor.py --image_dir /var/segmentations --output_dir /var/results --voreen_tool_path /home/software/voreen-src-unix-nightly/bin/ "$@"
elif [ "$mode" = "etdrs" ]
then
    python /home/OCTA-graph-extraction/faz_segmentation.py --source_dir /var/segmentations --source_files "/**/*.png" --output_dir /var/faz &&\
    python /home/OCTA-graph-extraction/graph_feature_extractor.py --image_dir /var/segmentations --output_dir /var/results --voreen_tool_path /home/software/voreen-src-unix-nightly/bin/ --ETDRS --faz_dir /var/faz "$@"
else
    echo "Mode $mode does not exist. Choose 'faz_seg', 'full' or 'etdrs'."
    exit 1
fi