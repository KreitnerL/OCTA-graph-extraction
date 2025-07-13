ARG NUMBER_OF_PROCESSES

FROM debian:bullseye-slim

RUN apt-get update && apt-get install -y --no-install-recommends apt-utils

# Install dependencies
RUN apt install -y build-essential clinfo cmake ffmpeg freeglut3-dev g++ libavcodec-dev libavformat-dev libboost-all-dev libdevil-dev libgdcm-dev libglew-dev libhdf5-dev liblz4-dev libqt5svg5-dev libswscale-dev libtiff5-dev libvtk9-dev opencl-headers mesa-common-dev mesa-utils ninja-build qt5-qmake qtbase5-dev qtbase5-dev-tools wget

# Build VTK
RUN wget https://www.vtk.org/files/release/9.5/VTK-9.5.0.tar.gz
RUN mkdir /home/software
RUN tar -xf VTK-9.5.0.tar.gz -C /home/software
RUN mv /home/software/VTK-9.5.0 /home/software/vtk_source
RUN mkdir /home/software/vtk
RUN cd /home/software/vtk_source && cmake . -B /home/software/vtk
RUN cd /home/software/vtk && make -j $NUMBER_OF_PROCESSES

# Build Voreen
RUN wget https://github.com/voreen-project/voreen/archive/refs/tags/voreen-5.3.0.tar.gz
RUN tar -xf voreen-5.3.0.tar.gz -C /home/software
RUN printf 'set(VRN_MODULE_BASE ON CACHE BOOL "" FORCE)\nset(VRN_MODULE_BIGDATAIMAGEPROCESSING ON CACHE BOOL "" FORCE)\nset(VRN_MODULE_CONNEXE ON CACHE BOOL "" FORCE)\nset(VRN_MODULE_DEPRECATED OFF CACHE BOOL "" FORCE)\nset(VRN_MODULE_DEVIL ON CACHE BOOL "" FORCE)\nset(VRN_MODULE_ENSEMBLEANALYSIS ON CACHE BOOL "" FORCE)\nset(VRN_MODULE_EXPERIMENTAL OFF CACHE BOOL "" FORCE)\nset(VRN_MODULE_FFMPEG OFF CACHE BOOL "" FORCE)\nset(VRN_MODULE_FLOWANALYSIS ON CACHE BOOL "" FORCE)\nset(VRN_MODULE_GDCM OFF CACHE BOOL "" FORCE)\nset(VRN_MODULE_HDF5 ON CACHE BOOL "" FORCE)\nset(VRN_MODULE_ITK OFF CACHE BOOL "" FORCE)\nset(VRN_MODULE_ITK_GENERATED OFF CACHE BOOL "" FORCE)\nset(VRN_MODULE_OPENCL OFF CACHE BOOL "" FORCE)\nset(VRN_MODULE_OPENMP OFF CACHE BOOL "" FORCE)\nset(VRN_MODULE_PLOTTING ON CACHE BOOL "" FORCE)\nset(VRN_MODULE_POI OFF CACHE BOOL "" FORCE)\nset(VRN_MODULE_PVM ON CACHE BOOL "" FORCE)\nset(VRN_MODULE_PYTHON ON CACHE BOOL "" FORCE)\nset(VRN_MODULE_RANDOMWALKER ON CACHE BOOL "" FORCE)\nset(VRN_MODULE_SAMPLE OFF CACHE BOOL "" FORCE)\nset(VRN_MODULE_SEGY ON CACHE BOOL "" FORCE)\nset(VRN_MODULE_STAGING ON CACHE BOOL "" FORCE)\nset(VRN_MODULE_STEREOSCOPY ON CACHE BOOL "" FORCE)\nset(VRN_MODULE_SURFACE ON CACHE BOOL "" FORCE)\nset(VRN_MODULE_TIFF OFF CACHE BOOL "" FORCE)\nset(VRN_MODULE_ULTRAMICROSCOPYDEPLOYMENT OFF CACHE BOOL "" FORCE)\nset(VRN_MODULE_VESSELNETWORKANALYSIS ON CACHE BOOL "" FORCE)\nset(VRN_MODULE_VOLUMELABELING OFF CACHE BOOL "" FORCE)\nset(VRN_MODULE_VTK ON CACHE BOOL "" FORCE)\nset(VRN_MODULE_ZIP ON CACHE BOOL "" FORCE)\nset(VRN_NON_INTERACTIVE OFF CACHE BOOL "" FORCE)\nset(VRN_OPENGL_COMPATIBILITY_PROFILE OFF CACHE BOOL "" FORCE)\nset(VRN_PRECOMPILED_HEADER OFF CACHE BOOL "" FORCE)\nset(VRN_USE_GENERIC_FILE_WATCHER OFF CACHE BOOL "" FORCE)\nset(VRN_USE_HDF5_VERSION 1.10 CACHE STRING "" FORCE)\nset(VRN_USE_SSE41 ON CACHE BOOL "" FORCE)\nset(VRN_VESSELNETWORKANALYSIS_BUILD ON CACHE BOOL "" FORCE)\nset(VRN_BUILD_VOREENTOOL ON CACHE BOOL "" FORCE)\nset(VTK_DIR /home/software/vtk/lib/cmake/vtk-9.5 CACHE PATH "" FORCE)' >> /home/software/voreen-voreen-5.3.0/voreen/config-default.cmake
RUN cd /home/software/voreen-voreen-5.3.0/voreen && cmake .
RUN cd /home/software/voreen-voreen-5.3.0/voreen && make -j $NUMBER_OF_PROCESSES

# Set proper permissions for Voreen data directory to allow any user to write
RUN chmod 777 -R /home/software/voreen-voreen-5.3.0/voreen/data

RUN echo "Successfully build image!"
