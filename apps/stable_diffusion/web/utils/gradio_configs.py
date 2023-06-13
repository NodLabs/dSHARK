import os
import shutil
import tempfile
import gradio
from time import time

gradio_tmp_imgs_folder = os.path.join(os.getcwd(), "shark_tmp/")
gradio_tmp_galleries_folder = os.path.join(gradio_tmp_imgs_folder, "galleries")


# Clear all gradio tmp images
def clear_gradio_tmp_imgs_folder():
    if not os.path.exists(gradio_tmp_imgs_folder):
        return

    # clear all gradio tmp files created by generation galleries
    print(
        "Clearing gradio temporary image files from a prior run. This may take some time..."
    )
    image_files = [
        filename
        for filename in os.listdir(gradio_tmp_imgs_folder)
        if os.path.isfile(os.path.join(gradio_tmp_imgs_folder, filename))
        and filename.startswith("tmp")
        and filename.endswith(".png")
    ]
    if len(image_files) > 0:
        cleanup_start = time()
        for filename in image_files:
            os.remove(gradio_tmp_imgs_folder + filename)
        print(
            f"Clearing generation temporary image files took {time() - cleanup_start:4f} seconds"
        )
    else:
        print("no generation temporary files to clear")

    # Clear all gradio tmp files created by output galleries
    if os.path.exists(gradio_tmp_galleries_folder):
        cleanup_start = time()
        shutil.rmtree(gradio_tmp_galleries_folder, ignore_errors=True)
        print(
            f"Clearing output gallery temporary image files took {time() - cleanup_start:4f} seconds"
        )
    else:
        print("no output gallery temporary files to clear")


# Overwrite save_pil_to_file from gradio to save tmp images generated by gradio into our own tmp folder
def save_pil_to_file(pil_image, dir=None):
    if not os.path.exists(gradio_tmp_imgs_folder):
        os.mkdir(gradio_tmp_imgs_folder)
    file_obj = tempfile.NamedTemporaryFile(
        delete=False, suffix=".png", dir=gradio_tmp_imgs_folder
    )
    pil_image.save(file_obj)
    return file_obj


# Register save_pil_to_file override
gradio.processing_utils.save_pil_to_file = save_pil_to_file
