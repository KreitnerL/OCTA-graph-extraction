#!/bin/bash
echo "[Info] Mode: $1"
mode=$1
shift

if [ "$mode" = "roi" ]
then
    python /home/OCTA-graph-extraction/ROI_cropping.py --input_dir /var/images --output_dir /var/results "$@" && \
    chmod -R 777 /var/results
elif [ "$mode" = "faz_seg" ]
then
    python /home/OCTA-graph-extraction/faz_segmentation.py --source_files "/var/segmentations/**/*.*" --output_dir /var/faz "$@" && \
    chmod -R 777 /var/faz
elif [ "$mode" = "graph_extraction_full" ]
then 
    python /home/OCTA-graph-extraction/graph_feature_extractor.py --image_files "/var/segmentations/**/*.*" --output_dir /var/results --voreen_tool_path /home/software/voreen-src-unix-nightly/bin/ "$@" && \
    chmod -R 777 /var/results
elif [ "$mode" = "graph_extraction_etdrs" ]
then
    python /home/OCTA-graph-extraction/graph_feature_extractor.py --image_files "/var/segmentations/**/*.*" --faz_dir /var/faz --output_dir /var/results --voreen_tool_path /home/software/voreen-src-unix-nightly/bin/ --ETDRS "$@" && \
    chmod -R 777 /var/results
elif  [ "$mode" = "etdrs_pipeline" ]
then
    python /home/OCTA-graph-extraction/faz_segmentation.py --source_files "/var/segmentations/**/*.*" --output_dir /var/faz &&\
    python /home/OCTA-graph-extraction/graph_feature_extractor.py --image_files "/var/segmentations/**/*.*" --output_dir /var/results --voreen_tool_path /home/software/voreen-src-unix-nightly/bin/ --ETDRS --faz_dir /var/faz "$@" && \
    chmod -R 777 /var/results && \
    chmod -R 777 /var/faz
elif  [ "$mode" = "analysis" ]
then
    python /home/OCTA-graph-extraction/generate_analysis_summary.py --source_dir /var/graph_files --output_dir /var/results --faz_files "/var/faz/**/*.*" "$@" && \
    chmod -R 777 /var/results
else
    echo "Mode $mode does not exist. Choose 'roi', 'faz_seg', 'graph_extraction_full', 'graph_extraction_etdrs' or 'etdrs_pipeline'."
    exit 1
fi