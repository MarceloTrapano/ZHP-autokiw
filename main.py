import tempfile
from pathlib import Path
from fastapi import File, Form, Response, UploadFile
import modal
from src import ZhpColor, AutoKiwBuilder
import subprocess
import tempfile
from pathlib import Path


def svg_to_png(svg_code: str, size: int = 1200) -> bytes:
    with tempfile.TemporaryDirectory() as tmp:
        svg_path = Path(tmp) / "out.svg"
        png_path = Path(tmp) / "out.png"
        svg_path.write_text(svg_code, encoding="utf-8")

        subprocess.run(
            [
                "inkscape",
                str(svg_path),
                "--export-type=png",
                f"--export-filename={png_path}",
                "-w", str(size),
                "-h", str(size),
            ],
            check=True,
            capture_output=True,
        )
        return png_path.read_bytes()


image = (
    modal.Image.from_registry(
        "nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04",
        add_python="3.11",
    )
    .apt_install("fontconfig", "wget", "libcairo2", "inkscape")
    .pip_install(
        "onnxruntime-gpu==1.20.2",
        "rembg",
        "svgwrite",
        "pillow",
        "fastapi",
        "python-multipart",
    )
    .run_commands(
        "mkdir -p /root/.rembg/models/bria-rmbg/ && "
        "wget https://github.com/danielgatis/rembg/releases/download/v0.0.0/bria-rmbg-2.0.onnx "
        "-O /root/.rembg/models/bria-rmbg/bria-rmbg.onnx"
    )
    .add_local_dir("assets", remote_path="/root/assets", copy=True)
    .run_commands(
        "mkdir -p /usr/share/fonts/truetype/museo",
        "cp /root/assets/*.otf /usr/share/fonts/truetype/museo/ 2>/dev/null || true",
        "fc-cache -fv",
        "ls -la /root/assets/*.otf",
        "fc-list | grep -i museo",
    )
    .add_local_dir("src", remote_path="/root/src")
)

app = modal.App("zhp-generator")


@app.cls(gpu="T4", image=image)
class ZhpGeneratorService:
    @modal.enter()
    def setup(self):
        from rembg import new_session
        try:
            self.session = new_session(
                providers=["CUDAExecutionProvider", "CPUExecutionProvider"]
            )
        except Exception as e:
            self.session = new_session(providers=["CPUExecutionProvider"])
        import onnxruntime as ort

    @modal.fastapi_endpoint(method="POST")
    def generate(
        self,
        image_file: UploadFile = File(...),
        main_text: str = Form(...),
        secondary_text: str = Form(""),
        color_name: str = Form("green_base"),
        use_cutout: bool = Form(False),
        author: str = Form(""),
        logo_file: UploadFile = File(None),
    ):
        tmp_files = []

        img_suffix = Path(image_file.filename).suffix or ".jpg"
        with tempfile.NamedTemporaryFile(delete=False, suffix=img_suffix) as tmp_img:
            tmp_img.write(image_file.file.read())
            tmp_img_path = tmp_img.name
            tmp_files.append(tmp_img_path)

        selected_color = getattr(ZhpColor, color_name, ZhpColor.green_base)

        builder = (
            AutoKiwBuilder(session=self.session)
            .set_image(tmp_img_path)
            .set_main_text(main_text)
            .set_secondary_text(secondary_text)
            .set_color(selected_color)
            .set_cutout(use_cutout)
            .set_author(author)
        )

        if hasattr(builder, "set_author"):
            builder.set_author(author)
        elif hasattr(builder, "author"):
            builder.author = author

        if logo_file and logo_file.filename:
            logo_suffix = Path(logo_file.filename).suffix or ".png"
            with tempfile.NamedTemporaryFile(delete=False, suffix=logo_suffix) as tmp_logo:
                tmp_logo.write(logo_file.file.read())
                tmp_logo_path = tmp_logo.name
                tmp_files.append(tmp_logo_path)
                builder.set_logo_path(tmp_logo_path)

        svg_code = builder.build()

        png_bytes = svg_to_png(
            svg_code
        )

        return Response(content=png_bytes, media_type="image/png")
