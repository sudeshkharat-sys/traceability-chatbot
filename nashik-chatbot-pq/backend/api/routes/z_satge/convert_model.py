import io
import logging
import tempfile
import os
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import Response

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/convert-model", tags=["convert-model"])

SUPPORTED = {'.wrl', '.obj', '.stl', '.glb', '.gltf'}

@router.post("/")
async def convert_model(file: UploadFile = File(...)):
    """
    Accept WRL / OBJ / STL / GLB and return a simplified GLB.
    Runs server-side mesh decimation so large CAD files become browser-renderable.
    """
    try:
        import trimesh
    except ImportError:
        raise HTTPException(status_code=500, detail="trimesh not installed on server")

    ext = os.path.splitext(file.filename or '')[1].lower()
    if ext not in SUPPORTED:
        raise HTTPException(status_code=400, detail=f"Unsupported format: {ext}. Supported: {', '.join(SUPPORTED)}")

    data = await file.read()
    logger.info(f"convert_model: received {file.filename} ({len(data)/1024/1024:.1f} MB)")

    try:
        # Write to temp file so trimesh can detect format by extension
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(data)
            tmp_path = tmp.name

        try:
            scene = trimesh.load(tmp_path, force='scene')
        finally:
            os.unlink(tmp_path)

        # Merge all meshes into one for easier processing
        if isinstance(scene, trimesh.Scene):
            meshes = [g for g in scene.geometry.values() if isinstance(g, trimesh.Trimesh)]
            if not meshes:
                raise HTTPException(status_code=422, detail="No renderable geometry found in file")
            merged = trimesh.util.concatenate(meshes)
        elif isinstance(scene, trimesh.Trimesh):
            merged = scene
        else:
            raise HTTPException(status_code=422, detail="Could not parse geometry from file")

        original_faces = len(merged.faces)
        logger.info(f"convert_model: loaded {original_faces:,} faces")

        # Decimate if too heavy — target max 80k faces for smooth browser rendering
        TARGET_FACES = 80_000
        if original_faces > TARGET_FACES:
            ratio = TARGET_FACES / original_faces
            merged = merged.simplify_quadric_decimation(face_count=TARGET_FACES)
            logger.info(f"convert_model: decimated {original_faces:,} → {len(merged.faces):,} faces (ratio {ratio:.3f})")

        # Export as GLB
        glb_bytes = merged.export(file_type='glb')
        out_size = len(glb_bytes) / 1024 / 1024
        logger.info(f"convert_model: output GLB {out_size:.1f} MB")

        return Response(
            content=glb_bytes,
            media_type="model/gltf-binary",
            headers={"Content-Disposition": f'attachment; filename="{os.path.splitext(file.filename)[0]}.glb"'}
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"convert_model error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Conversion failed: {str(e)}")
