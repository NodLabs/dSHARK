def pytest_addoption(parser):
    # Attaches SHARK command-line arguments to the pytest machinery.
    parser.addoption(
        "--benchmark",
        action="store_true",
        default="False",
        help="Pass option to benchmark and write results.csv",
    )
    parser.addoption(
        "--onnx_bench",
        action="store_true",
        default="False",
        help="Add ONNX benchmark results to pytest benchmarks.",
    )
    parser.addoption(
        "--tf32",
        action="store",
        default="False",
        help="Use TensorFloat-32 calculations.",
    )
    parser.addoption(
        "--save_repro",
        action="store_true",
        default="False",
        help="Pass option to save reproduction artifacts to SHARK/shark_tmp/test_case/",
    )
    parser.addoption(
        "--save_fails",
        action="store_true",
        default="False",
        help="Save reproduction artifacts for a test case only if it fails. Default is False.",
    )
    parser.addoption(
        "--ci",
        action="store_true",
        default="False",
        help="Enables uploading of reproduction artifacts upon test case failure during iree-compile or validation. Must be passed with --ci_sha option ",
    )
    parser.addoption(
        "--ci_sha",
        action="store",
        default="None",
        help="Passes the github SHA of the CI workflow to include in google storage directory for reproduction artifacts.",
    )
    parser.addoption(
        "--local_tank_cache",
        action="store",
        default="",
        help="Specify the directory in which all downloaded shark_tank artifacts will be cached.",
    )
    parser.addoption(
        "--tank_url",
        type=str,
        default="gs://shark_tank/latest",
        help="URL to bucket from which to download SHARK tank artifacts. Default is gs://shark_tank/latest",
    )
    parser.addoption(
        "--tuner_config",
        type=str,
        default=None,
        help="Look for SHARK-tuned model MLIR with this tuning config. Either cpu, cuda, vulkan, or a target triple.",
    )
    parser.addoption(
        "--set_fw_intraop_thread_count",
        type=int,
        default=1,
        help="Ask PyTorch/TF to use this number of threads for intraop parallelism.",
    )
    parser.addoption(
        "--set_fw_interop_thread_count",
        type=int,
        default=1,
        help="Ask PyTorch/TF to use this number of threads for interop parallelism.",
    )
    parser.addoption(
        "--set_iree_thread_count",
        type=int,
        default=None,
        help="sets thread count for IREE benchmarks.",
    )
