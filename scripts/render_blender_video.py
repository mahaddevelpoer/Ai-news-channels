from __future__ import annotations

import json
import math
from pathlib import Path

import bpy


ROOT_DIR = Path(__file__).resolve().parents[1]
ASSETS_DIR = ROOT_DIR / "assets"
TIMINGS_PATH = ROOT_DIR / "output" / "timings.json"
SCRIPT_PATH = ROOT_DIR / "output" / "script.json"
VIDEO_PATH = ROOT_DIR / "output" / "render.mp4"
FRAMES_DIR = ROOT_DIR / "output" / "frames"
FRAME_MANIFEST = ROOT_DIR / "output" / "frame_manifest.json"

STUDIO_FBX = ASSETS_DIR / "studio" / "scifi-tron-studio-baked" / "source" / "3.fbx"
IDLE_ANCHOR_FBX = ASSETS_DIR / "models" / "Breathing Idle.fbx"
TALKING_ANCHOR_FBX = ASSETS_DIR / "models" / "Talking.fbx"
BREAKING_ANIMATION = ASSETS_DIR / "animation.mp4"

FPS = 24


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()


def material(name: str, color: tuple[float, float, float, float]) -> bpy.types.Material:
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = color
    return mat


def import_fbx(filepath: Path, collection_name: str) -> list[bpy.types.Object]:
    if not filepath.exists():
        raise FileNotFoundError(f"Required FBX asset is missing: {filepath}")

    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=str(filepath))
    imported = [obj for obj in bpy.data.objects if obj not in before]
    collection = bpy.data.collections.new(collection_name)
    bpy.context.scene.collection.children.link(collection)
    for obj in imported:
        for source_collection in list(obj.users_collection):
            source_collection.objects.unlink(obj)
        collection.objects.link(obj)
    return imported


def object_bounds(objects: list[bpy.types.Object]) -> tuple[float, float, float]:
    coords = []
    for obj in objects:
        if obj.type in {"MESH", "ARMATURE", "EMPTY"}:
            coords.extend([obj.matrix_world @ corner for corner in obj.bound_box])
    if not coords:
        return (1, 1, 2)
    return (
        max(v.x for v in coords) - min(v.x for v in coords),
        max(v.y for v in coords) - min(v.y for v in coords),
        max(v.z for v in coords) - min(v.z for v in coords),
    )


def set_group_transform(objects: list[bpy.types.Object], location: tuple, scale: float, rotation_z: float = 0) -> None:
    empty = bpy.data.objects.new(f"{objects[0].name}_group", None)
    bpy.context.scene.collection.objects.link(empty)
    for obj in objects:
        if obj.parent is None:
            obj.parent = empty
            obj.matrix_parent_inverse.identity()
    empty.location = location
    empty.scale = (scale, scale, scale)
    empty.rotation_euler[2] = math.radians(rotation_z)


def add_text(name: str, text: str, location: tuple, size: float, mat: bpy.types.Material) -> bpy.types.Object:
    bpy.ops.object.text_add(location=location, rotation=(math.radians(72), 0, 0))
    obj = bpy.context.object
    obj.name = name
    obj.data.body = text
    obj.data.align_x = "CENTER"
    obj.data.align_y = "CENTER"
    obj.data.size = size
    obj.data.extrude = 0.008
    obj.data.materials.append(mat)
    return obj


def add_cube(name: str, location: tuple, scale: tuple, mat: bpy.types.Material) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(mat)
    return obj


def add_breaking_movie_plane() -> bpy.types.Object:
    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, -2.15, 2.0), rotation=(math.radians(76), 0, 0))
    plane = bpy.context.object
    plane.name = "breaking_animation_screen"
    plane.scale = (2.9, 1.65, 1)

    mat = bpy.data.materials.new("breaking_animation_material")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    bsdf = nodes.get("Principled BSDF")
    tex = nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(str(BREAKING_ANIMATION))
    tex.image.source = "MOVIE"
    tex.image_user.frame_duration = 240
    tex.image_user.use_auto_refresh = True
    mat.node_tree.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    mat.node_tree.links.new(tex.outputs["Color"], bsdf.inputs["Emission Color"])
    bsdf.inputs["Emission Strength"].default_value = 1.4
    plane.data.materials.append(mat)
    return plane


def keyframe_camera(camera: bpy.types.Object, frame: int, loc: tuple, rot: tuple, lens: float = 30) -> None:
    camera.location = loc
    camera.rotation_euler = tuple(math.radians(v) for v in rot)
    camera.data.lens = lens
    camera.keyframe_insert("location", frame=frame)
    camera.keyframe_insert("rotation_euler", frame=frame)
    camera.data.keyframe_insert("lens", frame=frame)


def keyframe_obj(obj: bpy.types.Object, frame: int, loc: tuple | None = None, scale: tuple | None = None) -> None:
    if loc is not None:
        obj.location = loc
        obj.keyframe_insert("location", frame=frame)
    if scale is not None:
        obj.scale = scale
        obj.keyframe_insert("scale", frame=frame)


def set_visibility(obj: bpy.types.Object, start: int, end: int, total_frames: int) -> None:
    obj.hide_viewport = True
    obj.hide_render = True
    obj.keyframe_insert("hide_viewport", frame=max(1, start - 1))
    obj.keyframe_insert("hide_render", frame=max(1, start - 1))
    obj.hide_viewport = False
    obj.hide_render = False
    obj.keyframe_insert("hide_viewport", frame=start)
    obj.keyframe_insert("hide_render", frame=start)
    obj.keyframe_insert("hide_viewport", frame=end)
    obj.keyframe_insert("hide_render", frame=end)
    obj.hide_viewport = True
    obj.hide_render = True
    obj.keyframe_insert("hide_viewport", frame=min(total_frames, end + 1))
    obj.keyframe_insert("hide_render", frame=min(total_frames, end + 1))


def loop_actions(objects: list[bpy.types.Object], total_frames: int) -> None:
    for obj in objects:
        action = obj.animation_data.action if obj.animation_data else None
        curves = getattr(action, "fcurves", []) if action else []
        for curve in curves:
            try:
                curve.modifiers.new(type="CYCLES")
            except RuntimeError:
                pass
        if obj.type == "ARMATURE" and action:
            action.use_fake_user = True


def add_anchor_motion(objects: list[bpy.types.Object], start: int, end: int, intensity: float) -> None:
    roots = [obj for obj in objects if obj.parent is None]
    if not roots:
        roots = objects[:1]
    for root in roots:
        for frame in range(start, end + 1, 12):
            phase = math.sin(frame * 0.18)
            root.location.z += 0.01 * intensity * phase
            root.rotation_euler[2] = math.radians(1.4 * intensity * phase)
            root.keyframe_insert("location", frame=frame)
            root.keyframe_insert("rotation_euler", frame=frame)


def truncate(text: str, length: int = 62) -> str:
    return text if len(text) <= length else text[: length - 3] + "..."


def main() -> None:
    clear_scene()
    with TIMINGS_PATH.open("r", encoding="utf-8") as handle:
        timings = json.load(handle)
    with SCRIPT_PATH.open("r", encoding="utf-8") as handle:
        script = json.load(handle)

    total_frames = max(240, int(timings["total_duration_ms"] / 1000 * FPS))
    FRAMES_DIR.mkdir(parents=True, exist_ok=True)
    for old_frame in FRAMES_DIR.glob("frame_*.png"):
        old_frame.unlink()

    bpy.context.scene.frame_start = 1
    bpy.context.scene.frame_end = total_frames
    bpy.context.scene.render.fps = FPS
    bpy.context.scene.render.resolution_x = 1280
    bpy.context.scene.render.resolution_y = 720
    bpy.context.scene.render.image_settings.file_format = "PNG"
    try:
        bpy.context.scene.render.engine = "BLENDER_EEVEE_NEXT"
    except TypeError:
        bpy.context.scene.render.engine = "BLENDER_EEVEE"

    white = material("overlay_white", (1, 1, 1, 1))
    red = material("ticker_red", (0.9, 0.02, 0.02, 1))
    black = material("ticker_black", (0.01, 0.01, 0.012, 1))

    studio = import_fbx(STUDIO_FBX, "existing_studio")
    set_group_transform(studio, (0, 0, 0), 1.0)

    anchor_a = import_fbx(IDLE_ANCHOR_FBX, "anchor_a_idle")
    anchor_b = import_fbx(TALKING_ANCHOR_FBX if TALKING_ANCHOR_FBX.exists() else IDLE_ANCHOR_FBX, "anchor_b_talking")
    set_group_transform(anchor_a, (-1.6, -0.3, 0.02), 0.012, rotation_z=10)
    set_group_transform(anchor_b, (1.6, -0.3, 0.02), 0.012, rotation_z=-10)
    loop_actions(anchor_a + anchor_b, total_frames)

    breaking_plane = add_breaking_movie_plane()
    ticker_bar = add_cube("ticker_bar", (0, -1.85, 0.44), (4.7, 0.05, 0.28), black)
    red_strip = add_cube("ticker_red_strip", (0, -1.87, 0.62), (4.7, 0.04, 0.08), red)
    add_text("date_text", script["created_at"][:16].replace("T", " UTC "), (2.25, -1.9, 0.73), 0.08, white)

    bpy.ops.object.light_add(type="AREA", location=(0, -2.7, 4.6))
    light = bpy.context.object
    light.name = "newsroom_softbox"
    light.data.energy = 800
    light.data.size = 5

    bpy.ops.object.camera_add(location=(0, -5.0, 2.45), rotation=(math.radians(66), 0, 0))
    camera = bpy.context.object
    bpy.context.scene.camera = camera
    keyframe_camera(camera, 1, (0, -5.4, 2.45), (66, 0, 0), 26)
    keyframe_camera(camera, 72, (0, -4.5, 2.25), (66, 0, 0), 30)

    keyframe_obj(breaking_plane, 1, loc=(0, -2.15, 2.0), scale=(3.2, 1.8, 1))
    keyframe_obj(breaking_plane, 62, loc=(0, -2.15, 2.0), scale=(3.2, 1.8, 1))
    keyframe_obj(breaking_plane, 100, loc=(-1.78, -2.05, 2.58), scale=(1.08, 0.62, 1))

    render_plan = [{"source_frame": 1, "duration_ms": 1800}]
    for segment in timings["segments"]:
        start = max(100, int(segment["start_ms"] / 1000 * FPS))
        end = max(start + 30, int(segment["end_ms"] / 1000 * FPS))
        is_a = segment["reporter"] == "A"
        x = -1.25 if is_a else 1.25

        keyframe_obj(breaking_plane, max(1, start - 38), loc=(0, -2.15, 2.0), scale=(3.2, 1.8, 1))
        keyframe_obj(breaking_plane, start, loc=(-1.78 if is_a else 1.78, -2.05, 2.58), scale=(1.08, 0.62, 1))

        keyframe_camera(camera, max(1, start - 42), (0, -4.5, 2.25), (66, 0, 0), 30)
        keyframe_camera(camera, start + 42, (x, -2.25, 1.78), (72, 0, -7 if is_a else 7), 46)
        keyframe_camera(camera, end, (x, -2.25, 1.78), (72, 0, -7 if is_a else 7), 46)

        add_anchor_motion(anchor_a if is_a else anchor_b, start, end, 1.0)
        add_anchor_motion(anchor_b if is_a else anchor_a, start, end, 0.25)

        headline = add_text(f"headline_{segment['index']:02d}", truncate(segment["headline"]), (0, -1.93, 0.74), 0.1, white)
        ticker = add_text(
            f"ticker_{segment['index']:02d}",
            f"BREAKING NEWS  |  {segment['source']}  |  {segment['published_at'][:16].replace('T', ' UTC ')}",
            (0, -1.93, 0.47),
            0.073,
            white,
        )
        graphic = add_cube(f"small_graphic_{segment['index']:02d}", (-2.25 if is_a else 2.25, -1.93, 1.02), (0.55, 0.04, 0.32), red)
        for obj in (headline, ticker, graphic):
            set_visibility(obj, start, end, total_frames)

        keyframe_obj(breaking_plane, min(total_frames, end + 30), loc=(0, -2.15, 2.0), scale=(3.2, 1.8, 1))
        keyframe_camera(camera, min(total_frames, end + 42), (0, -4.5, 2.25), (66, 0, 0), 30)
        render_plan.extend(
            [
                {"source_frame": max(1, start - 20), "duration_ms": 900},
                {"source_frame": min(total_frames, start + 42), "duration_ms": segment["duration_ms"]},
                {"source_frame": min(total_frames, end + 30), "duration_ms": 550},
            ]
        )

    keyframe_camera(camera, total_frames - 72, (0, -4.4, 2.3), (66, 0, 0), 30)
    keyframe_camera(camera, total_frames, (0, -5.5, 2.45), (66, 0, 0), 26)
    keyframe_obj(breaking_plane, total_frames - 72, loc=(-1.78, -2.05, 2.58), scale=(1.08, 0.62, 1))
    keyframe_obj(breaking_plane, total_frames, loc=(0, -2.15, 2.0), scale=(3.2, 1.8, 1))
    render_plan.append({"source_frame": total_frames, "duration_ms": 1800})

    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT_DIR / "output" / "scene.blend"))
    manifest = []
    for idx, item in enumerate(render_plan, start=1):
        frame_path = FRAMES_DIR / f"frame_{idx:04d}.png"
        bpy.context.scene.frame_set(item["source_frame"])
        bpy.context.scene.render.filepath = str(frame_path)
        bpy.ops.render.render(write_still=True)
        manifest.append({"file": str(frame_path), "duration_ms": item["duration_ms"]})

    with FRAME_MANIFEST.open("w", encoding="utf-8") as handle:
        json.dump({"frames": manifest}, handle, indent=2)

    print(f"Rendered {len(manifest)} studio keyframes to {FRAMES_DIR}")


if __name__ == "__main__":
    main()
