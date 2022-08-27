# Copyright 2020 The Nod Team. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from shark.shark_runner import SharkRunner
from shark.iree_utils.compile_utils import export_iree_module_to_vmfb
from shark.iree_utils.benchmark_utils import (
    build_benchmark_args,
    run_benchmark_module,
)
from shark.parser import shark_args
from datetime import datetime
import time
import csv
import os


class OnnxFusionOptions(object):
    def __init__(self):
        self.disable_gelu = False
        self.disable_layer_norm = False
        self.disable_attention = False
        self.disable_skip_layer_norm = False
        self.disable_embed_layer_norm = False
        self.disable_bias_skip_layer_norm = False
        self.disable_bias_gelu = False
        self.enable_gelu_approximation = False
        self.use_mask_index = False
        self.no_attention_mask = False


class SharkBenchmarkRunner(SharkRunner):
    # SharkRunner derived class with Benchmarking capabilities.
    def __init__(
        self,
        mlir_module: str,
        function_name: str = "forward",
        device: str = "none",
        mlir_dialect: str = "linalg",
    ):
        self.device = shark_args.device if device == "none" else device
        self.frontend_model = None
        self.vmfb_file = None
        self.mlir_dialect = mlir_dialect
        SharkRunner.__init__(
            self,
            mlir_module,
            function_name,
            device,
            self.mlir_dialect,
        )
        if self.vmfb_file == None:
            self.vmfb_file = export_iree_module_to_vmfb(
                mlir_module, device, shark_args.repro_dir, self.mlir_dialect
            )

    def setup_cl(self, input_tensors):
        self.benchmark_cl = build_benchmark_args(
            self.vmfb_file,
            self.device,
            input_tensors,
            mlir_dialect=self.mlir_dialect,
        )
        print(self.benchmark_cl)

    def benchmark_frontend(self, modelname):
        if self.mlir_dialect in ["linalg", "torch"]:
            return self.benchmark_torch(modelname)
        elif self.mlir_dialect in ["mhlo", "tf"]:
            return self.benchmark_tf(modelname)

    def benchmark_torch(self, modelname):
        import torch
        from tank.model_utils import get_torch_model

        if self.device == "gpu":
            torch.set_default_tensor_type(torch.cuda.FloatTensor)
        else:
            torch.set_default_tensor_type(torch.FloatTensor)
        torch_device = torch.device(
            "cuda:0" if self.device == "gpu" else "cpu"
        )
        HFmodel, input = get_torch_model(modelname)[:2]
        frontend_model = HFmodel.model
        frontend_model.to(torch_device)
        input.to(torch_device)

        for i in range(shark_args.num_warmup_iterations):
            frontend_model.forward(input)

        begin = time.time()
        for i in range(shark_args.num_iterations):
            out = frontend_model.forward(input)
            if i == shark_args.num_iterations - 1:
                end = time.time()
                break
        print(
            f"Torch benchmark:{shark_args.num_iterations/(end-begin)} iter/second, Total Iterations:{shark_args.num_iterations}"
        )
        return [
            f"{shark_args.num_iterations/(end-begin)}",
            f"{((end-begin)/shark_args.num_iterations)*1000}",
        ]

    def benchmark_tf(self, modelname):
        import tensorflow as tf
        from tank.model_utils_tf import get_tf_model

        model, input, = get_tf_model(
            modelname
        )[:2]
        frontend_model = model

        for i in range(shark_args.num_warmup_iterations):
            frontend_model.forward(*input)

        begin = time.time()
        for i in range(shark_args.num_iterations):
            out = frontend_model.forward(*input)
            if i == shark_args.num_iterations - 1:
                end = time.time()
                break
        print(
            f"TF benchmark:{shark_args.num_iterations/(end-begin)} iter/second, Total Iterations:{shark_args.num_iterations}"
        )
        return [
            f"{shark_args.num_iterations/(end-begin)}",
            f"{((end-begin)/shark_args.num_iterations)*1000}",
        ]

    def benchmark_c(self):
        print(self.benchmark_cl)
        result = run_benchmark_module(self.benchmark_cl)
        print(f"Shark-IREE-C benchmark:{result} iter/second")
        return [f"{result}", f"{1000/result}"]

    def benchmark_python(self, inputs):
        input_list = [x for x in inputs]
        for i in range(shark_args.num_warmup_iterations):
            self.run(input_list)

        begin = time.time()
        for i in range(shark_args.num_iterations):
            out = self.run(input_list)
            if i == shark_args.num_iterations - 1:
                end = time.time()
        print(
            f"Shark-IREE Python benchmark:{shark_args.num_iterations/(end-begin)} iter/second, Total Iterations:{shark_args.num_iterations}"
        )
        return [
            f"{shark_args.num_iterations/(end-begin)}",
            f"{((end-begin)/shark_args.num_iterations)*1000}",
        ]

    def benchmark_onnx(self, modelname, inputs):
        if self.device == "gpu":
            print(
                "Currently GPU benchmarking on ONNX is not supported in SHARK."
            )
            return ["N/A", "N/A"]
        else:
            from onnxruntime.transformers.benchmark import run_onnxruntime
            from onnxruntime.transformers.huggingface_models import MODELS
            from onnxruntime.transformers.benchmark_helper import (
                ConfigModifier,
                Precision,
            )
            import psutil

            if modelname == "microsoft/MiniLM-L12-H384-uncased":
                modelname = "bert-base-uncased"
            if modelname not in MODELS:
                print(
                    f"{modelname} is currently not supported in ORT's HF. Check \
https://github.com/microsoft/onnxruntime/blob/master/onnxruntime/python/tools/transformers/huggingface_models.py \
for currently supported models. Exiting benchmark ONNX."
                )
                return ["N/A", "N/A"]
            use_gpu = self.device == "gpu"
            num_threads = psutil.cpu_count(logical=False)
            batch_sizes = [1]
            sequence_lengths = [128]
            cache_dir = os.path.join(".", "cache_models")
            onnx_dir = os.path.join(".", "onnx_models")
            verbose = False
            input_counts = [1]
            optimize_onnx = True
            validate_onnx = False
            disable_ort_io_binding = False
            use_raw_attention_mask = True
            model_fusion_statistics = {}
            overwrite = False
            model_source = "pt"  # Either "pt" or "tf"
            provider = None
            config_modifier = ConfigModifier(None)
            onnx_args = OnnxFusionOptions()
            result = run_onnxruntime(
                use_gpu,
                provider,
                (modelname,),
                None,
                config_modifier,
                Precision.FLOAT32,
                num_threads,
                batch_sizes,
                sequence_lengths,
                shark_args.num_iterations,
                input_counts,
                optimize_onnx,
                validate_onnx,
                cache_dir,
                onnx_dir,
                verbose,
                overwrite,
                disable_ort_io_binding,
                use_raw_attention_mask,
                model_fusion_statistics,
                model_source,
                onnx_args,
            )
            print(
                f"ONNX ORT-benchmark:{result[0]['QPS']} iter/second, Total Iterations:{shark_args.num_iterations}"
            )
            return [
                result[0]["QPS"],
                result[0]["average_latency_ms"],
            ]

    def get_metadata(self, modelname):
        with open("./tank/pytorch/torch_model_list.csv", mode="r") as csvfile:
            torch_reader = csv.reader(csvfile, delimiter=",")
            fields = next(torch_reader)
            for row in torch_reader:
                torch_model_name = row[0]
                param_count = row[4]
                model_tags = row[5]
                model_notes = row[6]
                if torch_model_name == modelname:
                    return [param_count, model_tags, model_notes]

    def compare_bench_results(self, baseline: str, result: str):
        # Takes two numbers represented as strings and returns "<n>x slower/faster", as in "result is <n>x slower than baseline".
        a = float(baseline)
        b = float(result)
        if a < b:
            # result slower than baseline
            comparison = (b - a) / a
            comp_str = f"{round(comparison, 2)}x slower"
        elif a > b:
            # result faster than baseline
            comparison = a / b
            comp_str = f"{round(comparison, 2)}x faster"
        else:
            comp_str = "equal"
        return comp_str

    def benchmark_all_csv(
        self, inputs: tuple, modelname, dynamic, device_str, frontend
    ):
        self.setup_cl(inputs)
        field_names = [
            "model",
            "engine",
            "dialect",
            "device",
            "shape_type",
            "data_type",
            "iter/sec",
            "ms/iter",
            "vs. PyTorch/TF",
            "iterations",
            "param_count",
            "tags",
            "notes",
            "datetime",
        ]
        engines = ["frontend", "shark_python", "shark_iree_c"]
        if shark_args.onnx_bench == True:
            engines.append("onnxruntime")

        if not os.path.exists("bench_results.csv"):
            with open("bench_results.csv", mode="w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(field_names)

        with open("bench_results.csv", mode="a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=field_names)
            bench_result = {}
            bench_result["model"] = modelname
            if dynamic == True:
                bench_result["shape_type"] = "dynamic"
            else:
                bench_result["shape_type"] = "static"
            bench_result["device"] = device_str
            bench_result["data_type"] = inputs[0].dtype
            for e in engines:
                if e == "frontend":
                    bench_result["engine"] = frontend
                    (
                        bench_result["iter/sec"],
                        bench_result["ms/iter"],
                    ) = self.benchmark_frontend(modelname)
                    self.frontend_result = bench_result["ms/iter"]
                    bench_result["vs. PyTorch/TF"] = "="
                    (
                        bench_result["param_count"],
                        bench_result["tags"],
                        bench_result["notes"],
                    ) = self.get_metadata(modelname)

                elif e == "shark_python":
                    bench_result["engine"] = "shark_python"
                    (
                        bench_result["iter/sec"],
                        bench_result["ms/iter"],
                    ) = self.benchmark_python(inputs)

                    bench_result[
                        "vs. PyTorch/TF"
                    ] = self.compare_bench_results(
                        self.frontend_result, bench_result["ms/iter"]
                    )
                    (
                        bench_result["param_count"],
                        bench_result["tags"],
                        bench_result["notes"],
                    ) = ["", "", ""]

                elif e == "shark_iree_c":
                    bench_result["engine"] = "shark_iree_c"
                    (
                        bench_result["iter/sec"],
                        bench_result["ms/iter"],
                    ) = self.benchmark_c()

                    bench_result[
                        "vs. PyTorch/TF"
                    ] = self.compare_bench_results(
                        self.frontend_result, bench_result["ms/iter"]
                    )
                    (
                        bench_result["param_count"],
                        bench_result["tags"],
                        bench_result["notes"],
                    ) = ["", "", ""]

                elif e == "onnxruntime":
                    bench_result["engine"] = "onnxruntime"
                    (
                        bench_result["iter/sec"],
                        bench_result["ms/iter"],
                    ) = self.benchmark_onnx(modelname, inputs)

                bench_result["dialect"] = self.mlir_dialect
                bench_result["iterations"] = shark_args.num_iterations
                bench_result["datetime"] = str(datetime.now())
                writer.writerow(bench_result)
