cmake_minimum_required(VERSION 3.21)
project(DynaGraphHPC VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
option(DYNAGRAPH_WARNINGS_AS_ERRORS "Treat project compiler warnings as errors" OFF)

find_package(OpenMP REQUIRED COMPONENTS CXX)
include(CTest)

function(dynagraph_set_warnings target)
    if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
        target_compile_options(${target} PRIVATE
            -Wall -Wextra -Wpedantic -Wconversion -Wshadow)
        if(DYNAGRAPH_WARNINGS_AS_ERRORS)
            target_compile_options(${target} PRIVATE -Werror)
        endif()
    endif()
endfunction()

add_library(dynagraph STATIC
    src/adaptive/adaptive_sssp.cpp
    src/dynamic/incremental_sssp.cpp
    src/algorithms/delta_stepping.cpp
    src/algorithms/dijkstra.cpp
    src/project_info.cpp
    src/graph/csr_graph.cpp
    src/graph/edge_list_io.cpp)
add_library(DynaGraph::dynagraph ALIAS dynagraph)
target_include_directories(dynagraph PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>)
target_compile_features(dynagraph PUBLIC cxx_std_17)
target_compile_definitions(dynagraph PRIVATE DYNAGRAPH_VERSION="${PROJECT_VERSION}")
target_link_libraries(dynagraph PUBLIC OpenMP::OpenMP_CXX)
dynagraph_set_warnings(dynagraph)

add_executable(dynagraph_cli apps/dynagraph_cli.cpp)
target_link_libraries(dynagraph_cli PRIVATE DynaGraph::dynagraph)
dynagraph_set_warnings(dynagraph_cli)

add_executable(dynagraph_bench apps/dynagraph_bench.cpp src/benchmark/replay.cpp)
target_link_libraries(dynagraph_bench PRIVATE DynaGraph::dynagraph)
dynagraph_set_warnings(dynagraph_bench)

if(BUILD_TESTING)
    add_subdirectory(tests)
endif()
