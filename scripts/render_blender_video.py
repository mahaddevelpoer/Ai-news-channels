from __future__ import annotations

import json
import math
from pathlib import Path

import bpy
from mathutils import Vector


ROOT_DIR = Path(__file__).resolve().parents[1]
ASSETS_DIR = ROOT_DIR / "assets"
TIMINGS_PATH = ROOT_DIR / "output" / "timings.json"
SCRIPT_PATH = ROOT_DIR / "output" / "script.json"
FRAMES_DIR = ROOT_DIR / "output" / "frames"

STUDIO_FBX = ASSETS_DIR / "studio" / "scifi-tron-studio-baked" / "source" / "3.fbx"
TALKING_ANCHOR_FBX = ASSETS_DIR / "models" / "Talking.fbx"
IDLE_ANCHOR_FBX = ASSETS_DIR / "models" / "Breathing Idle.fbx"
BREAKING_ANIMATION = ASSETS_DIR / "animation.mp4"

FPS = 12


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()


def material(name: str, color: tuple[float, float, float, float], emission: float = 0) -> bpy.types.Material:
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = color
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = color
    bsdf.inputs["Roughness"].default_value = 0.58
    if emission:
        bsdf.inputs["Emission Color"].default_value = color
        bsdf.inputs["Emission Strength"].default_value = emission
    return mat


def import_fbx(filepath: Path, collection_name: str) -> list[bpy.types.Object]:
    if not filepath.exists():
        raise FileNotFoundError(f"Missing asset: {filepath}")
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


def bounds(objects: list[bpy.types.Object]) -> tuple[Vector, Vector]:
    points = []
    for obj in objects:
        if hasattr(obj, "bound_box"):
            points.extend(obj.matrix_world @ Vector(corner) for corner in obj.bound_box)
    if not points:
        return Vector((-1, -1, 0)), Vector((1, 1, 2))
    return (
        Vector((min(p.x for p in points), min(p.y for p in points), min(p.z for p in points))),
        Vector((max(p.x for p in points), max(p.y for p in points), max(p.z for p in points))),
    )


def normalize_group(objects: list[bpy.types.Object], name: str, location: tuple, target_height: float, rotation_z: float = 0) -> bpy.types.Object:
    low, high = bounds(objects)
    center = (low + high) / 2
    height = max(0.001, high.z - low.z)
    scale = target_height / height

    empty = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(empty)
    for obj in objects:
        if obj.parent is None:
            obj.location -= center
            obj.parent = empty
            obj.matrix_parent_inverse.identity()

    empty.location = location
    empty.scale = (scale, scale, scale)
    empty.rotation_euler[2] = math.radians(rotation_z)
    return empty


def add_cube(name: str, location: tuple, scale: tuple, mat: bpy.types.Material) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(mat)
    return obj


def add_text(name: str, text: str, location: tuple, size: float, mat: bpy.types.Material) -> bpy.types.Object:
    bpy.ops.object.text_add(location=location, rotation=(math.radians(72), 0, 0))
    obj = bpy.context.object
    obj.name = name
    obj.data.body = text
    obj.data.align_x = "CENTER"
    obj.data.align_y = "CENTER"
    obj.data.size = size
    obj.data.extrude = 0.01
    obj.data.materials.append(mat)
    return obj


def add_breaking_screen() -> bpy.types.Object:
    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, -2.25, 1.7), rotation=(math.radians(72), 0, 0))
    plane = bpy.context.object
    plane.name = "breaking_news_video_screen"
    plane.scale = (3.25, 1.85, 1)

    mat = bpy.data.materials.new("breaking_news_movie_material")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    tex = mat.node_tree.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(str(BREAKING_ANIMATION))
    tex.image.source = "MOVIE"
    tex.image_user.frame_duration = 240
    tex.image_user.use_auto_refresh = True
    mat.node_tree.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    mat.node_tree.links.new(tex.outputs["Color"], bsdf.inputs["Emission Color"])
    bsdf.inputs["Emission Strength"].default_value = 1.8
    plane.data.materials.append(mat)
    return plane


def keyframe(obj: bpy.types.Object, frame: int, loc: tuple | None = None, scale: tuple | None = None, rot: tuple | None = None) -> None:
    if loc is not None:
        obj.location = loc
        obj.keyframe_insert("location", frame=frame)
    if scale is not None:
        obj.scale = scale
        obj.keyframe_insert("scale", frame=frame)
    if rot is not None:
        obj.rotation_euler = tuple(math.radians(v) for v in rot)
        obj.keyframe_insert("rotation_euler", frame=frame)


def keyframe_camera(camera: bpy.types.Object, frame: int, loc: tuple, rot: tuple, lens: float) -> None:
    keyframe(camera, frame, loc=loc, rot=rot)
    camera.data.lens = lens
    camera.data.keyframe_insert("lens", frame=frame)


def show_between(obj: bpy.types.Object, start: int, end: int, total: int) -> None:
    obj.hide_render = True
    obj.hide_viewport = True
    obj.keyframe_insert("hide_render", frame=max(1, start - 1))
    obj.keyframe_insert("hide_viewport", frame=max(1, start - 1))
    obj.hide_render = False
    obj.hide_viewport = False
    obj.keyframe_insert("hide_render", frame=start)
    obj.keyframe_insert("hide_viewport", frame=start)
    obj.keyframe_insert("hide_render", frame=end)
    obj.keyframe_insert("hide_viewport", frame=end)
    obj.hide_render = True
    obj.hide_viewport = True
    obj.keyframe_insert("hide_render", frame=min(total, end + 1))
    obj.keyframe_insert("hide_viewport", frame=min(total, end + 1))


def loop_imported_actions(objects: list[bpy.types.Object]) -> None:
    for obj in objects:
        action = obj.animation_data.action if obj.animation_data else None
        for curve in getattr(action, "fcurves", []) if action else []:
            try:
                curve.modifiers.new(type="CYCLES")
            except RuntimeError:
                pass


def animate_anchor(root: bpy.types.Object, start: int, end: int, active: bool) -> None:
    step = 8 if active else 18
    base = root.location.copy()
    for frame in range(start, end + 1, step):
        phase = math.sin(frame * (0.22 if active else 0.1))
        root.location = base + Vector((0, 0, (0.045 if active else 0.018) * phase))
        root.rotation_euler[2] = math.radians((2.0 if active else 0.55) * phase)
        root.keyframe_insert("location", frame=frame)
        root.keyframe_insert("rotation_euler", frame=frame)


def truncate(text: str, length: int = 68) -> str:
    return text if len(text) <= length else text[: length - 3] + "..."


def set_easing() -> None:
    for obj in bpy.data.objects:
        if obj.animation_data and obj.animation_data.action:
            for curve in getattr(obj.animation_data.action, "fcurves", []):
                for point in curve.keyframe_points:
                    point.interpolation = "BEZIER"


def main() -> None:
    clear_scene()
    with TIMINGS_PATH.open("r", encoding="utf-8") as handle:
        timings = json.load(handle)
    with SCRIPT_PATH.open("r", encoding="utf-8") as handle:
        script = json.load(handle)

    total_frames = max(160, int(timings["total_duration_ms"] / 1000 * FPS))
    FRAMES_DIR.mkdir(parents=True, exist_ok=True)
    for old in FRAMES_DIR.glob("frame_*.png"):
        old.unlink()

    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = total_frames
    scene.render.fps = FPS
    scene.render.resolution_x = 1280
    scene.render.resolution_y = 720
    scene.render.resolution_percentage = 100
    scene.render.filepath = str(FRAMES_DIR / "frame_")
    scene.render.image_settings.file_format = "PNG"
    try:
        scene.render.engine = "BLENDER_EEVEE_NEXT"
        scene.eevee.taa_render_samples = 16
    except Exception:
        scene.render.engine = "BLENDER_EEVEE"

    white = material("news_white", (1, 1, 1, 1), 0.2)
    red = material("news_red", (0.9, 0.02, 0.02, 1), 0.3)
    black = material("news_black", (0.015, 0.015, 0.018, 1))
    blue = material("news_blue", (0.02, 0.08, 0.18, 1), 0.12)

    studio_objects = import_fbx(STUDIO_FBX, "existing_3d_studio")
    studio_root = normalize_group(studio_objects, "studio_root", (0, 0.65, 0.0), 3.2)
    add_cube("news_floor_fill", (0, 0, -0.03), (7.2, 5.2, 0.05), black)
    add_cube("news_desk", (0, -0.65, 0.72), (4.4, 0.72, 0.48), blue)
    add_cube("news_desk_red_band", (0, -1.03, 0.88), (4.5, 0.05, 0.18), red)

    anchor_a_objects = import_fbx(TALKING_ANCHOR_FBX if TALKING_ANCHOR_FBX.exists() else IDLE_ANCHOR_FBX, "anchor_a")
    anchor_b_objects = import_fbx(TALKING_ANCHOR_FBX if TALKING_ANCHOR_FBX.exists() else IDLE_ANCHOR_FBX, "anchor_b")
    anchor_a = normalize_group(anchor_a_objects, "anchor_a_root", (-1.35, -0.2, 0.03), 1.62, rotation_z=7)
    anchor_b = normalize_group(anchor_b_objects, "anchor_b_root", (1.35, -0.2, 0.03), 1.62, rotation_z=-7)
    loop_imported_actions(anchor_a_objects + anchor_b_objects)

    breaking_screen = add_breaking_screen()
    ticker_bar = add_cube("ticker_bar", (0, -1.95, 0.4), (5.2, 0.04, 0.28), black)
    red_strip = add_cube("ticker_red_strip", (0, -1.98, 0.58), (5.2, 0.04, 0.08), red)
    add_text("show_time", script["created_at"][:16].replace("T", " UTC "), (2.42, -2.0, 0.72), 0.075, white)

    bpy.ops.object.light_add(type="AREA", location=(0, -2.8, 4.0))
    key_light = bpy.context.object
    key_light.name = "large_newsroom_key_light"
    key_light.data.energy = 900
    key_light.data.size = 5.5
    bpy.ops.object.light_add(type="POINT", location=(-2.5, -1.5, 2.2))
    bpy.context.object.data.energy = 90
    bpy.ops.object.light_add(type="POINT", location=(2.5, -1.5, 2.2))
    bpy.context.object.data.energy = 90

    bpy.ops.object.camera_add(location=(0, -5.1, 2.15), rotation=(math.radians(68), 0, 0))
    camera = bpy.context.object
    bpy.context.scene.camera = camera
    keyframe_camera(camera, 1, (0, -5.3, 2.25), (67, 0, 0), 26)
    keyframe_camera(camera, int(1.5 * FPS), (0, -4.25, 2.02), (68, 0, 0), 31)

    keyframe(breaking_screen, 1, loc=(0, -2.25, 1.74), scale=(3.35, 1.9, 1))
    keyframe(breaking_screen, int(1.5 * FPS), loc=(0, -2.25, 1.74), scale=(3.35, 1.9, 1))

    for segment in timings["segments"]:
        start = max(1, int(segment["start_ms"] / 1000 * FPS))
        end = max(start + 12, int(segment["end_ms"] / 1000 * FPS))
        is_a = segment["reporter"] == "A"
        side_x = -1.22 if is_a else 1.22
        screen_x = 1.83 if is_a else -1.83

        keyframe(breaking_screen, max(1, start - int(0.75 * FPS)), loc=(0, -2.25, 1.74), scale=(3.35, 1.9, 1))
        keyframe(breaking_screen, start, loc=(screen_x, -2.08, 2.28), scale=(1.03, 0.58, 1))
        keyframe_camera(camera, max(1, start - int(0.8 * FPS)), (0, -4.2, 2.03), (68, 0, 0), 31)
        keyframe_camera(camera, start + int(1.1 * FPS), (side_x, -2.15, 1.54), (73, 0, -7 if is_a else 7), 49)
        keyframe_camera(camera, end, (side_x, -2.15, 1.54), (73, 0, -7 if is_a else 7), 49)

        animate_anchor(anchor_a, start, end, active=is_a)
        animate_anchor(anchor_b, start, end, active=not is_a)

        headline = add_text(f"headline_{segment['index']:02d}", truncate(segment["headline"]), (0, -2.02, 0.7), 0.09, white)
        ticker = add_text(
            f"ticker_{segment['index']:02d}",
            f"BREAKING NEWS | {segment['source']} | {segment['published_at'][:16].replace('T', ' UTC ')}",
            (0, -2.03, 0.44),
            0.064,
            white,
        )
        bug = add_cube(f"live_bug_{segment['index']:02d}", (-2.35 if is_a else 2.35, -2.02, 0.83), (0.55, 0.04, 0.26), red)
        live = add_text(f"live_text_{segment['index']:02d}", "LIVE", (-2.35 if is_a else 2.35, -2.06, 0.84), 0.08, white)
        for obj in (headline, ticker, bug, live):
            show_between(obj, start, end, total_frames)

        keyframe(breaking_screen, min(total_frames, end + int(0.55 * FPS)), loc=(0, -2.25, 1.74), scale=(3.35, 1.9, 1))
        keyframe_camera(camera, min(total_frames, end + FPS), (0, -4.25, 2.02), (68, 0, 0), 31)

    keyframe_camera(camera, max(1, total_frames - int(1.8 * FPS)), (0, -4.2, 2.02), (68, 0, 0), 31)
    keyframe_camera(camera, total_frames, (0, -5.45, 2.25), (67, 0, 0), 26)
    keyframe(breaking_screen, total_frames, loc=(0, -2.25, 1.74), scale=(3.35, 1.9, 1))

    set_easing()
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT_DIR / "output" / "scene.blend"))
    bpy.ops.render.render(animation=True)
    print(f"Rendered animated studio sequence at {FPS} FPS to {FRAMES_DIR}")


if __name__ == "__main__":
    main()
