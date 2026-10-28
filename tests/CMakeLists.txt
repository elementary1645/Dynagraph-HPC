foreach(test_name IN ITEMS project_info openmp csr_graph edge_list_io dijkstra delta_stepping
                           incremental_sssp incremental_failure adaptive_sssp adaptive_failure)
    add_executable(test_${test_name} test_${test_name}.cpp)
    target_link_libraries(test_${test_name} PRIVATE DynaGraph::dynagraph)
    dynagraph_set_warnings(test_${test_name})
    add_test(NAME ${test_name} COMMAND test_${test_name})
    set_tests_properties(${test_name} PROPERTIES TIMEOUT 10)
endforeach()

set_tests_properties(incremental_sssp incremental_failure PROPERTIES TIMEOUT 60)

set_tests_properties(openmp PROPERTIES
    PROCESSORS 2
    LABELS "smoke;openmp"
    ENVIRONMENT "OMP_NUM_THREADS=2;OMP_THREAD_LIMIT=2;OMP_DYNAMIC=FALSE")

add_test(NAME cli_launch COMMAND dynagraph_cli)
set_tests_properties(cli_launch PROPERTIES
    TIMEOUT 10 PASS_REGULAR_EXPRESSION "Phase 2B sequential and parallel SSSP")
add_test(NAME cli_help COMMAND dynagraph_cli --help)
set_tests_properties(cli_help PROPERTIES
    TIMEOUT 10 PASS_REGULAR_EXPRESSION "Usage: dynagraph_cli")
add_test(NAME cli_version COMMAND dynagraph_cli --version)
set_tests_properties(cli_version PROPERTIES
    TIMEOUT 10 PASS_REGULAR_EXPRESSION "DynaGraph-HPC ${PROJECT_VERSION}")
add_test(NAME cli_invalid_argument COMMAND dynagraph_cli --unsupported)
set_tests_properties(cli_invalid_argument PROPERTIES TIMEOUT 10 WILL_FAIL TRUE)

add_test(NAME cli_sssp COMMAND ${CMAKE_COMMAND}
    -DCLI=$<TARGET_FILE:dynagraph_cli>
    -DWORK=${CMAKE_CURRENT_BINARY_DIR}/cli_sssp
    -P ${CMAKE_CURRENT_SOURCE_DIR}/test_cli_sssp.cmake)
set_tests_properties(cli_sssp PROPERTIES TIMEOUT 20)

find_package(Threads REQUIRED)
target_link_libraries(test_adaptive_sssp PRIVATE Threads::Threads)
set_tests_properties(adaptive_sssp adaptive_failure PROPERTIES TIMEOUT 120 PROCESSORS 2
    ENVIRONMENT "OMP_NUM_THREADS=2;OMP_THREAD_LIMIT=8;OMP_DYNAMIC=FALSE")
target_link_libraries(test_delta_stepping PRIVATE Threads::Threads)
set_tests_properties(delta_stepping PROPERTIES TIMEOUT 120 PROCESSORS 2
    ENVIRONMENT "OMP_NUM_THREADS=2;OMP_THREAD_LIMIT=8;OMP_DYNAMIC=FALSE")

add_executable(test_delta_failure test_delta_failure.cpp)
target_link_libraries(test_delta_failure PRIVATE DynaGraph::dynagraph)
dynagraph_set_warnings(test_delta_failure)
add_test(NAME delta_failure COMMAND test_delta_failure)
set_tests_properties(delta_failure PROPERTIES TIMEOUT 60 PROCESSORS 2
    ENVIRONMENT "OMP_NUM_THREADS=2;OMP_THREAD_LIMIT=2;OMP_DYNAMIC=FALSE")
set_tests_properties(cli_sssp PROPERTIES
    ENVIRONMENT "OMP_NUM_THREADS=2;OMP_THREAD_LIMIT=8;OMP_DYNAMIC=FALSE")

# Standard-library-only artifact tooling; no Python dependency for library-only builds.
find_package(Python3 3.8 REQUIRED COMPONENTS Interpreter)
add_test(NAME workload_artifacts COMMAND ${Python3_EXECUTABLE}
    ${CMAKE_CURRENT_SOURCE_DIR}/test_workloads.py)
add_test(NAME workload_loader COMMAND ${Python3_EXECUTABLE}
    ${CMAKE_CURRENT_SOURCE_DIR}/test_workload_loader.py $<TARGET_FILE:dynagraph_cli>)
set_tests_properties(workload_artifacts workload_loader PROPERTIES TIMEOUT 60
    ENVIRONMENT "PYTHONDONTWRITEBYTECODE=1;PYTHONHASHSEED=0")

add_test(NAME benchmark_replay COMMAND ${Python3_EXECUTABLE}
    ${CMAKE_CURRENT_SOURCE_DIR}/test_benchmark_replay.py $<TARGET_FILE:dynagraph_bench>)
set_tests_properties(benchmark_replay PROPERTIES TIMEOUT 120 PROCESSORS 2
    ENVIRONMENT "PYTHONDONTWRITEBYTECODE=1;PYTHONHASHSEED=0;OMP_NUM_THREADS=2;OMP_THREAD_LIMIT=2;OMP_DYNAMIC=FALSE")

add_executable(test_benchmark_timing test_benchmark_timing.cpp
    ../src/benchmark/timing.cpp ../src/benchmark/replay.cpp)
target_include_directories(test_benchmark_timing PRIVATE "${PROJECT_BINARY_DIR}/generated")
target_link_libraries(test_benchmark_timing PRIVATE DynaGraph::dynagraph)
dynagraph_set_warnings(test_benchmark_timing)
add_test(NAME benchmark_timing COMMAND test_benchmark_timing)
set_tests_properties(benchmark_timing PROPERTIES TIMEOUT 30
    ENVIRONMENT "OMP_NUM_THREADS=2;OMP_THREAD_LIMIT=2;OMP_DYNAMIC=FALSE")

add_test(NAME benchmark_experiment COMMAND ${Python3_EXECUTABLE}
    ${CMAKE_CURRENT_SOURCE_DIR}/test_benchmark_experiment.py $<TARGET_FILE:dynagraph_bench>)
set_tests_properties(benchmark_experiment PROPERTIES TIMEOUT 120 PROCESSORS 2
    ENVIRONMENT "PYTHONDONTWRITEBYTECODE=1;PYTHONHASHSEED=0;OMP_NUM_THREADS=2;OMP_THREAD_LIMIT=2;OMP_DYNAMIC=FALSE")

# Analysis uses Python 3.11+; existing artifact tooling retains its Python 3.8 minimum.
# No installation is performed by CMake. An approved pinned venv is optional.
set(DYNAGRAPH_ANALYSIS_PYTHON "${Python3_EXECUTABLE}" CACHE FILEPATH "Python for descriptive analysis tests")
execute_process(COMMAND "${DYNAGRAPH_ANALYSIS_PYTHON}" -c
    "import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)"
    RESULT_VARIABLE DYNAGRAPH_ANALYSIS_SUPPORTED)
if(DYNAGRAPH_ANALYSIS_SUPPORTED EQUAL 0)
    foreach(analysis_test IN ITEMS import stats)
        add_test(NAME analysis_${analysis_test} COMMAND "${DYNAGRAPH_ANALYSIS_PYTHON}"
            "${CMAKE_CURRENT_SOURCE_DIR}/test_analysis_${analysis_test}.py")
        set_tests_properties(analysis_${analysis_test} PROPERTIES TIMEOUT 60
            ENVIRONMENT "PYTHONDONTWRITEBYTECODE=1;PYTHONHASHSEED=0")
    endforeach()
    add_test(NAME analysis_integration COMMAND "${DYNAGRAPH_ANALYSIS_PYTHON}"
        "${CMAKE_CURRENT_SOURCE_DIR}/test_analysis_integration.py" $<TARGET_FILE:dynagraph_bench>)
    set_tests_properties(analysis_integration PROPERTIES TIMEOUT 120 PROCESSORS 2
        ENVIRONMENT "PYTHONDONTWRITEBYTECODE=1;PYTHONHASHSEED=0;OMP_NUM_THREADS=2;OMP_THREAD_LIMIT=2;OMP_DYNAMIC=FALSE")
    execute_process(COMMAND "${DYNAGRAPH_ANALYSIS_PYTHON}" -c
        "import sys; sys.path.insert(0, '${PROJECT_SOURCE_DIR}/benchmarks/python'); from analysis_figures import pinned_versions; pinned_versions()"
        RESULT_VARIABLE DYNAGRAPH_RENDERING_SUPPORTED OUTPUT_QUIET ERROR_QUIET)
    if(DYNAGRAPH_RENDERING_SUPPORTED EQUAL 0)
        add_test(NAME analysis_figures COMMAND "${DYNAGRAPH_ANALYSIS_PYTHON}"
            "${CMAKE_CURRENT_SOURCE_DIR}/test_analysis_figures.py")
        set_tests_properties(analysis_figures PROPERTIES TIMEOUT 120
            ENVIRONMENT "PYTHONDONTWRITEBYTECODE=1;PYTHONHASHSEED=0;MPLCONFIGDIR=${CMAKE_CURRENT_BINARY_DIR}/analysis-mpl-cache")
    else()
        message(STATUS "Pinned analysis renderer unavailable; analysis_figures is not registered")
    endif()
endif()

# Phase 5C-1: no production instrumentation or additional dependencies.
foreach(validation_target IN ITEMS system_correctness system_adversarial)
    add_executable(test_${validation_target} test_${validation_target}.cpp)
    target_link_libraries(test_${validation_target} PRIVATE DynaGraph::dynagraph)
    dynagraph_set_warnings(test_${validation_target})
    add_test(NAME ${validation_target} COMMAND test_${validation_target})
    set_tests_properties(${validation_target} PROPERTIES TIMEOUT 120 PROCESSORS 2 LABELS "validation-fast"
        ENVIRONMENT "OMP_NUM_THREADS=2;OMP_THREAD_LIMIT=2;OMP_DYNAMIC=FALSE")
endforeach()
option(DYNAGRAPH_ENABLE_VALIDATION_STRESS "Register bounded system validation stress" OFF)
option(DYNAGRAPH_ENABLE_VALIDATION_EXTENDED "Register manual extended system validation" OFF)
if(DYNAGRAPH_ENABLE_VALIDATION_STRESS)
    add_test(NAME system_stress COMMAND test_system_correctness --profile stress)
    set_tests_properties(system_stress PROPERTIES TIMEOUT 180 PROCESSORS 2 LABELS "validation-stress"
        ENVIRONMENT "OMP_NUM_THREADS=2;OMP_THREAD_LIMIT=2;OMP_DYNAMIC=FALSE")
endif()
add_test(NAME system_reproduction COMMAND ${Python3_EXECUTABLE}
    ${CMAKE_CURRENT_SOURCE_DIR}/test_system_reproduction.py $<TARGET_FILE:test_system_correctness>)
set_tests_properties(system_reproduction PROPERTIES TIMEOUT 120 PROCESSORS 2 LABELS "validation-fast"
    ENVIRONMENT "PYTHONDONTWRITEBYTECODE=1;PYTHONHASHSEED=0;OMP_NUM_THREADS=2;OMP_THREAD_LIMIT=2;OMP_DYNAMIC=FALSE")
if(DYNAGRAPH_ENABLE_VALIDATION_EXTENDED)
    add_test(NAME system_extended COMMAND test_system_correctness --profile extended)
    set_tests_properties(system_extended PROPERTIES TIMEOUT 900 PROCESSORS 2 LABELS "validation-extended"
        ENVIRONMENT "OMP_NUM_THREADS=2;OMP_THREAD_LIMIT=2;OMP_DYNAMIC=FALSE")
endif()
