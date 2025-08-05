#!/bin/bash

# Show help if requested
if [ "$1" = "--help" ] || [ "$1" = "-h" ] || [ -z "$1" ]; then
    echo "OCTA Graph Extraction Docker Shell"
    echo "Usage: $0 <mode> [options...]"
    echo ""
    echo "Available modes:"
    echo "  faz_seg               - Perform FAZ (Foveal Avascular Zone) segmentation"
    echo "  graph                 - Extract vessel graphs from segmentation masks"
    echo "  summary               - Generate analysis summary from extracted graphs"
    echo "  pipeline              - Complete pipeline (FAZ segmentation + full graph extraction)"
    echo "  etdrs_pipeline        - Complete ETDRS pipeline (FAZ segmentation + ETDRS graph extraction)"
    echo ""
    echo "Examples:"
    echo "  $0 graph_extraction_full --verbose"
    echo "  $0 etdrs_pipeline --bulge_size 2.5"
    echo "  $0 faz_seg --output_format png"
    echo ""
    echo "Options are passed through to the underlying Python scripts."
    echo "Use '$0 <mode> --help' to see mode-specific options."
    exit 0
fi

echo "[Info] Mode: $1"
mode=$1
shift
source /home/OCTA-graph-extraction/.venv/bin/activate

# Check if we're running in Docker (DooD setup)
if [ -f "/.dockerenv" ]; then
    echo "[Info] Running in Docker container (DooD mode)"
    # In DooD mode, use host paths that are mounted as volumes
    HOST_TMP_DIR=${HOST_TMP_DIR:-/tmp/voreen}
    HOST_OUTPUT_DIR=${HOST_OUTPUT_DIR:-/data/output}
    HOST_SRC_DIR=${HOST_SRC_DIR:-/data/src}
    
    # Map container paths to host paths for volume mounting with Voreen container
    TEMP_DIR=$HOST_TMP_DIR
    OUTPUT_DIR=$HOST_OUTPUT_DIR
    SRC_DIR=$HOST_SRC_DIR
else
    echo "[Info] Running on host system"
    # Use the mounted paths directly
    TEMP_DIR=/tmp/voreen
    OUTPUT_DIR=/data/output
    SRC_DIR=/data/src
fi

if [ "$mode" = "faz_seg" ]
then
    python /home/OCTA-graph-extraction/faz_segmentation.py --source_files "$SRC_DIR/**/*.*" --output_dir "$OUTPUT_DIR" "$@"
elif [ "$mode" = "graph" ]
then
    python /home/OCTA-graph-extraction/graph_feature_extractor.py --image_files "$SRC_DIR/**/*.*" --output_dir "$OUTPUT_DIR" --tmp_dir "$TEMP_DIR" "$@"
elif  [ "$mode" = "summary" ]
then
    python /home/OCTA-graph-extraction/generate_analysis_summary.py --source_dir "$OUTPUT_DIR" --output_dir "$OUTPUT_DIR" --faz_files "$OUTPUT_DIR/**/faz_*.png" --segmentation_dir "$SRC_DIR" "$@"
elif [ "$mode" = "pipeline" ]
then
    python /home/OCTA-graph-extraction/faz_segmentation.py --source_files "$SRC_DIR/**/*.*" --output_dir "$OUTPUT_DIR/faz" && \
    python /home/OCTA-graph-extraction/graph_feature_extractor.py --image_files "$SRC_DIR/**/*.*" --output_dir "$OUTPUT_DIR" --tmp_dir "$TEMP_DIR" && \
    python /home/OCTA-graph-extraction/generate_analysis_summary.py --source_dir "$OUTPUT_DIR" --output_dir "$OUTPUT_DIR" --faz_files "$OUTPUT_DIR/**/faz_*.png"  --segmentation_dir "$SRC_DIR" "$@"
elif  [ "$mode" = "etdrs_pipeline" ]
then
    python /home/OCTA-graph-extraction/faz_segmentation.py --source_files "$SRC_DIR/**/*.*" --output_dir "$OUTPUT_DIR/faz" && \
    python /home/OCTA-graph-extraction/graph_feature_extractor.py --image_files "$SRC_DIR/**/*.*" --output_dir "$OUTPUT_DIR" --tmp_dir "$TEMP_DIR" --etdrs --faz_dir "$OUTPUT_DIR/faz" && \
    python /home/OCTA-graph-extraction/generate_analysis_summary.py --source_dir "$OUTPUT_DIR" --output_dir "$OUTPUT_DIR" --faz_files "$OUTPUT_DIR/**/faz_*.png" --segmentation_dir "$SRC_DIR" --etdrs "$@"
else
    echo "Error: Mode '$mode' does not exist."
    echo ""
    echo "Available modes: faz_seg, graph, pipeline, etdrs_pipeline, summary"
    echo "Use '$0 --help' for detailed usage information."
    exit 1
fi