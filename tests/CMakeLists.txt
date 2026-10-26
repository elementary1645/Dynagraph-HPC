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
