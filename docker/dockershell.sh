#!/bin/bash
echo "[Info] Mode: $1"

if [ "$1" = "faz_seg" ]
then
    python /home/OCTA-graph-extraction/faz_segmentation.py --source_dir /var/segmentations --source_files "/**/*.png" --output_dir /var/faz 
elif [ "$1" = "full" ]
then 
    python /home/OCTA-graph-extraction/graph_feature_extractor.py --image_dir /var/segmentations --output_dir /var/results --bulge_size 3 --voreen_tool_path /home/software/voreen-src-unix-nightly/bin/ --colorize_graph True
elif [ "$1" = "etdrs" ]
then
    python /home/OCTA-graph-extraction/faz_segmentation.py --source_dir /var/segmentations --source_files "/**/*.png" --output_dir /var/faz 
    python /home/OCTA-graph-extraction/graph_feature_extractor.py --image_dir /var/segmentations --output_dir /var/results --bulge_size 3 --voreen_tool_path /home/software/voreen-src-unix-nightly/bin/ --colorize_graph True --ETDRS --faz_dir /var/faz
else
    echo "Mode $1 does not exist. Choose 'faz_seg', 'full' or 'etdrs'."
    exit 1
fi