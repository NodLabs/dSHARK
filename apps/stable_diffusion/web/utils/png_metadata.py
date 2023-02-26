import re
import os
from pathlib import Path
from apps.stable_diffusion.web.ui.txt2img_ui import (
    png_info_img,
    prompt,
    negative_prompt,
    steps,
    scheduler,
    guidance_scale,
    seed,
    width,
    height,
    custom_model,
    hf_model_id,
)
from apps.stable_diffusion.web.ui.utils import (
    get_custom_model_path,
    scheduler_list_txt2img,
    predefined_models,
)

re_param_code = r'\s*([\w ]+):\s*("(?:\\"[^,]|\\"|\\|[^\"])+"|[^,]*)(?:,|$)'
re_param = re.compile(re_param_code)
re_imagesize = re.compile(r"^(\d+)x(\d+)$")


def parse_generation_parameters(x: str):
    res = {}
    prompt = ""
    negative_prompt = ""
    done_with_prompt = False

    *lines, lastline = x.strip().split("\n")
    if len(re_param.findall(lastline)) < 3:
        lines.append(lastline)
        lastline = ""

    for i, line in enumerate(lines):
        line = line.strip()
        if line.startswith("Negative prompt:"):
            done_with_prompt = True
            line = line[16:].strip()

        if done_with_prompt:
            negative_prompt += ("" if negative_prompt == "" else "\n") + line
        else:
            prompt += ("" if prompt == "" else "\n") + line

    res["Prompt"] = prompt
    res["Negative prompt"] = negative_prompt

    for k, v in re_param.findall(lastline):
        v = v[1:-1] if v[0] == '"' and v[-1] == '"' else v
        m = re_imagesize.match(v)
        if m is not None:
            res[k + "-1"] = m.group(1)
            res[k + "-2"] = m.group(2)
        else:
            res[k] = v

    # Missing CLIP skip means it was set to 1 (the default)
    if "Clip skip" not in res:
        res["Clip skip"] = "1"

    hypernet = res.get("Hypernet", None)
    if hypernet is not None:
        res[
            "Prompt"
        ] += f"""<hypernet:{hypernet}:{res.get("Hypernet strength", "1.0")}>"""

    if "Hires resize-1" not in res:
        res["Hires resize-1"] = 0
        res["Hires resize-2"] = 0

    return res


def import_png_metadata(pil_data):
    try:
        png_info = pil_data.info["parameters"]
        metadata = parse_generation_parameters(png_info)
        png_hf_model_id = ""

        # Check for a model match with one of the local ckpt or safetensors files
        ckpt_path = get_custom_model_path()
        png_custom_model = os.path.join(ckpt_path, metadata["Model"])
        if not Path(png_custom_model).is_file():
            png_custom_model = "None"
        # Check for a model match with one of the default model list (ex: "Linaqruf/anything-v3.0")
        if metadata["Model"] in predefined_models:
            png_custom_model = metadata["Model"]
        # If nothing was found, fallback to hf model id
        if png_custom_model == "None":
            png_hf_model_id = metadata["Model"]

        outputs = {
            png_info_img: None,
            negative_prompt: metadata["Negative prompt"],
            steps: int(metadata["Steps"]),
            guidance_scale: float(metadata["CFG scale"]),
            seed: int(metadata["Seed"]),
            width: float(metadata["Size-1"]),
            height: float(metadata["Size-2"]),
            custom_model: png_custom_model,
            hf_model_id: png_hf_model_id,
        }
        if metadata["Prompt"]:
            outputs[prompt] = metadata["Prompt"]
        if metadata["Sampler"] in scheduler_list_txt2img:
            outputs[scheduler] = metadata["Sampler"]
        return outputs

    except Exception as ex:
        if pil_data and pil_data.info.get("parameters"):
            print("import_png_metadata failed with %s" % ex)
        pass

    return {
        png_info_img: None,
    }
