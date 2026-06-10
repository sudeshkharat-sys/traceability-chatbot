"""
3D model conversion endpoint: WRL/STP/STEP → GLB
Applies mesh simplification so huge files (e.g. 2 GB WRL/VRML) remain usable.
"""
import logging
import os
import tempfile
import traceback
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import Response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/z-stage", tags=["z_stage_convert"])

# Target face count after simplification (keeps the model lightweight in browser)
SIMPLIFY_TARGET_FACES = 80_000
# Files larger than this (bytes) trigger simplification
SIMPLIFY_THRESHOLD_BYTES = 20 * 1024 * 1024  # 20 MB

ALLOWED_EXTENSIONS = {"wrl", "stp", "step"}


def _convert_wrl_to_glb(src: Path) -> bytes:
    """Load a WRL/VRML file with trimesh and export as GLB bytes."""
    try:
        import trimesh
    except ImportError:
        raise HTTPException(
            status_code=500,
            detail="trimesh is not installed. Run: pip install trimesh[easy]",
        )

    logger.info("Loading WRL: %s (%.1f MB)", src.name, src.stat().st_size / 1e6)

    scene = trimesh.load(str(src), force="scene")

    # Flatten scene to a single mesh for simplification
    if isinstance(scene, trimesh.Scene):
        meshes = [g for g in scene.geometry.values() if isinstance(g, trimesh.Trimesh)]
        if not meshes:
            raise HTTPException(status_code=422, detail="No renderable geometry found in WRL file")
        mesh = trimesh.util.concatenate(meshes)
    elif isinstance(scene, trimesh.Trimesh):
        mesh = scene
    else:
        raise HTTPException(status_code=422, detail="Unsupported geometry type in WRL file")

    logger.info("Loaded mesh: %d faces, %d verts", len(mesh.faces), len(mesh.vertices))

    # Simplify if the mesh is very dense
    if len(mesh.faces) > SIMPLIFY_TARGET_FACES:
        logger.info("Simplifying to ~%d faces …", SIMPLIFY_TARGET_FACES)
        try:
            mesh = mesh.simplify_quadratic_decimation(SIMPLIFY_TARGET_FACES)
            logger.info("After simplification: %d faces", len(mesh.faces))
        except Exception as exc:
            # Simplification is best-effort; proceed with full mesh if it fails
            logger.warning("Simplification failed (%s), using original mesh", exc)

    # Export to GLB bytes
    glb_bytes = mesh.export(file_type="glb")
    logger.info("GLB size: %.2f MB", len(glb_bytes) / 1e6)
    return glb_bytes


def _convert_step_to_glb(src: Path) -> bytes:
    """Convert STEP file to GLB via pythonOCC + trimesh."""
    try:
        from OCC.Core.BRep import BRep_Builder
        from OCC.Core.TopoDS import TopoDS_Compound
        from OCC.Core.STEPControl import STEPControl_Reader
        from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh
        from OCC.Core.TopExp import TopExp_Explorer
        from OCC.Core.TopAbs import TopAbs_FACE
        from OCC.Core.BRep import BRep_Tool
        from OCC.Core.TopLoc import TopLoc_Location
        import numpy as np
        import trimesh
    except ImportError:
        raise HTTPException(
            status_code=500,
            detail=(
                "pythonOCC-core is required for STEP conversion. "
                "Install via: conda install -c conda-forge pythonocc-core"
            ),
        )

    reader = STEPControl_Reader()
    status = reader.ReadFile(str(src))
    if status != 1:
        raise HTTPException(status_code=422, detail="Failed to read STEP file")

    reader.TransferRoots()
    shape = reader.OneShape()

    # Tessellate
    mesh_gen = BRepMesh_IncrementalMesh(shape, 0.1, False, 0.5)
    mesh_gen.Perform()

    verts_all, faces_all = [], []
    offset = 0
    exp = TopExp_Explorer(shape, TopAbs_FACE)
    while exp.More():
        face = exp.Current()
        location = TopLoc_Location()
        triangulation = BRep_Tool.Triangulation(face, location)
        if triangulation is not None:
            n = triangulation.NbNodes()
            t = triangulation.NbTriangles()
            pts = np.array([[triangulation.Node(i).X(),
                             triangulation.Node(i).Y(),
                             triangulation.Node(i).Z()] for i in range(1, n + 1)])
            tris = np.array([[triangulation.Triangle(i).Get()[j] - 1 for j in range(3)]
                             for i in range(1, t + 1)])
            verts_all.append(pts)
            faces_all.append(tris + offset)
            offset += n
        exp.Next()

    if not verts_all:
        raise HTTPException(status_code=422, detail="No geometry tessellated from STEP file")

    mesh = trimesh.Trimesh(
        vertices=np.vstack(verts_all),
        faces=np.vstack(faces_all),
        process=True,
    )

    if len(mesh.faces) > SIMPLIFY_TARGET_FACES:
        try:
            mesh = mesh.simplify_quadratic_decimation(SIMPLIFY_TARGET_FACES)
        except Exception as exc:
            logger.warning("STEP simplification failed: %s", exc)

    return mesh.export(file_type="glb")


@router.post("/convert-model/")
async def convert_model(file: UploadFile = File(...)):
    """
    Convert a WRL/VRML or STEP file to GLB.
    Returns the GLB binary directly so the frontend can load it with Three.js GLTFLoader.
    Large meshes are automatically simplified to keep them browser-friendly.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    ext = file.filename.rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported format '.{ext}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # Stream upload to a temp file so we don't blow out RAM with a 2 GB file
    suffix = f".{ext}"
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp_path = Path(tmp.name)
            chunk_size = 4 * 1024 * 1024  # 4 MB chunks
            while True:
                chunk = await file.read(chunk_size)
                if not chunk:
                    break
                tmp.write(chunk)

        logger.info("Saved upload to %s (%.1f MB)", tmp_path, tmp_path.stat().st_size / 1e6)

        if ext == "wrl":
            glb_bytes = _convert_wrl_to_glb(tmp_path)
        else:
            glb_bytes = _convert_step_to_glb(tmp_path)

        return Response(
            content=glb_bytes,
            media_type="model/gltf-binary",
            headers={"Content-Disposition": f'attachment; filename="{Path(file.filename).stem}.glb"'},
        )

    except HTTPException:
        raise
    except Exception:
        logger.error("Model conversion error:\n%s", traceback.format_exc())
        raise HTTPException(status_code=500, detail="Model conversion failed. Check server logs.")
    finally:
        if tmp_path and tmp_path.exists():
            try:
                tmp_path.unlink()
            except Exception:
                pass
