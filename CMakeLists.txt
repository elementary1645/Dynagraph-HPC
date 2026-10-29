cmake_minimum_required(VERSION 3.21)
project(DynaGraphHPC VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
option(DYNAGRAPH_WARNINGS_AS_ERRORS "Treat project compiler warnings as errors" OFF)

find_package(OpenMP REQUIRED COMPONENTS CXX)
include(CTest)
option(DYNAGRAPH_FULL_VALIDATION "Require complete pinned analysis and exact test registrations" OFF)
if(DYNAGRAPH_FULL_VALIDATION AND NOT BUILD_TESTING)
    message(FATAL_ERROR "DYNAGRAPH_FULL_VALIDATION requires BUILD_TESTING=ON")
endif()

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

# Configure-time provenance; executable digest is observed by Python at run time.
execute_process(COMMAND git rev-parse HEAD WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}"
    OUTPUT_VARIABLE DYNAGRAPH_BENCH_REVISION RESULT_VARIABLE DYNAGRAPH_BENCH_GIT_RESULT OUTPUT_STRIP_TRAILING_WHITESPACE ERROR_QUIET)
execute_process(COMMAND git status --porcelain WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}"
    OUTPUT_VARIABLE DYNAGRAPH_BENCH_STATUS RESULT_VARIABLE DYNAGRAPH_BENCH_STATUS_RESULT OUTPUT_STRIP_TRAILING_WHITESPACE ERROR_QUIET)
if(NOT DYNAGRAPH_BENCH_GIT_RESULT EQUAL 0)
    set(DYNAGRAPH_BENCH_REVISION "unavailable")
endif()
if(NOT DYNAGRAPH_BENCH_STATUS_RESULT EQUAL 0)
    set(DYNAGRAPH_BENCH_DIRTY "unavailable")
elseif(DYNAGRAPH_BENCH_STATUS)
    set(DYNAGRAPH_BENCH_DIRTY "true")
else()
    set(DYNAGRAPH_BENCH_DIRTY "false")
endif()
string(TOUPPER "${CMAKE_BUILD_TYPE}" DYNAGRAPH_BENCH_BUILD_UPPER)
set(DYNAGRAPH_BENCH_FLAGS "${CMAKE_CXX_FLAGS} ${CMAKE_CXX_FLAGS_${DYNAGRAPH_BENCH_BUILD_UPPER}}; linker=${CMAKE_EXE_LINKER_FLAGS}; C++17; ${OpenMP_CXX_FLAGS}; -Wall -Wextra -Wpedantic -Wconversion -Wshadow; Werror=${DYNAGRAPH_WARNINGS_AS_ERRORS}")
set(DYNAGRAPH_BENCH_SANITIZERS "none_declared")
if(DYNAGRAPH_BENCH_FLAGS MATCHES "sanitize")
    set(DYNAGRAPH_BENCH_SANITIZERS "declared_in_flags")
endif()
configure_file(cmake/benchmark_build.hpp.in generated/dynagraph_benchmark_build.hpp @ONLY)
add_executable(dynagraph_bench apps/dynagraph_bench.cpp src/benchmark/replay.cpp src/benchmark/timing.cpp)
target_include_directories(dynagraph_bench PRIVATE "${CMAKE_CURRENT_BINARY_DIR}/generated")
target_link_libraries(dynagraph_bench PRIVATE DynaGraph::dynagraph)
dynagraph_set_warnings(dynagraph_bench)

if(BUILD_TESTING)
    add_subdirectory(tests)
endif()
