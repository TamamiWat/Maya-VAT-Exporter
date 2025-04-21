import os
import time
import maya.cmds as cmds

#----------------------------------------------------------------

""" Switches """
""" Mode Selected Meshes or All Meshes in scene """
Selected_Meshes = True

""" Global Vars """
X = 0
Y = 1
Z = 2

""" Functions """

def remap(xMin, xMax, yMin, yMax, t):
    if xMax - xMin == 0:
        return yMin  # or (yMin + yMax)/2
    return yMin + (yMax - yMin) * ((t - xMin) / (xMax - xMin))

""" Selects all the meshes in the scene """    
def select_all_meshes():
    #Gets the shape nodes of all meshes in the scene and makes them selected.  
    mesh_list = cmds.ls(type='mesh', long=True, noIntermediate=True)
    
    mesh_transforms=[]
    for shape in mesh_list:
        parents = cmds.listRelatives(shape, parent=True, fullPath=True)
        if parents:
            mesh_transforms.append(parents[0])

        if mesh_transforms:
            cmds.select(mesh_transforms, replace=True)

""" Returns a list of all meshes in the scene """    
def get_list_of_all_meshes():
    #Get all non-referenced meshes in the scene.  
    mesh_list = cmds.ls(type="mesh", long=True)

    mesh_no_ref_list = []
    for mesh in mesh_list:
        if cmds.referenceQuery(mesh, isNodeReferenced=True):
            continue
        if "Orig" not in mesh:
            mesh_no_ref_list.append(mesh)

    return mesh_no_ref_list

""" Returns a list of all selected meshes in the scene """   
def get_list_of_selected_meshes():
    #Returns a list of the nodes currently selected by the user.
    selected_mesh = cmds.ls(selection=True, long=True)
    return selected_mesh

""" Returns a list of all CTRL nurbs in scene """
def get_list_of_all_ctrl_nurbs():
    #Get all the shape nodes of a NURBS curve and extract only those that have CTRL in their name.
    nurbs_shape_list = cmds.ls(type = "nurbsCurve", long=True)
    ctrl_list = []

    for ctrl in nurbs_shape_list:
        if 'CTRL' in ctrl:
            parent = cmds.listRelatives(ctrl, parent=True, fullPath=True)
            if parent:
                ctrl_list.append(parent[0])

    return ctrl_list
    
""" Make sense of the currentUnit query command """
def demystify(fpsQuery):
    lookup = {
        "game": 15,
        "film": 24,
        "pal": 25,
        "ntsc": 30,
        "show": 48,
        "palf": 50,
        "ntscf": 60
    }
    if fpsQuery in lookup:
        return lookup[fpsQuery]
    else:
        return float(fpsQuery.replace("fps", ""))

def get_intermediate_shape(mesh):
    shapes = cmds.listRelatives(mesh, shapes=True, fullPath=True) or []
    for shape in shapes:
        if cmds.getAttr(shape + ".intermediateObject"):
            return shape
    print(f"[Warning] No Intermediate shape found for {mesh}")
    return None

"""" Returns vertex positions of intermediate object """
def get_unanimated_vertex_positions(mesh):
    intermediate_shape = get_intermediate_shape(mesh)
    if not intermediate_shape:
        return []

    count = cmds.polyEvaluate(intermediate_shape, vertex=True)
    positions = []
    # for i in range(count):
    #     vtx = f"{intermediate_shape}.vtx[{i}]"
    #     pos = cmds.pointPosition(vtx, world=True)
    #     positions.append(pos)
    positions = cmds.xform(f"{intermediate_shape}.vtx[*]", q=True, ws=True, t=True)
    positions = [positions[i:i+3] for i in range(0, len(positions), 3)]
    return positions

"""" Returns vertex normals of intermediate object """
def get_ununimated_vertex_normals(mesh):
    intermediate_shape = get_intermediate_shape(mesh)
    if not intermediate_shape:
        return []

    count = cmds.polyEvaluate(intermediate_shape, vertex=True)
    normals = []
    for i in range(count):
        vtx = f"{intermediate_shape}.vtx[{i}]"
        n = cmds.polyNormalPerVertex(vtx, query=True, xyz=True)
        normals.append(n[:3])  # First one normal vector
    return normals

""" Returns min and max of relative positions """
def get_min_max_of_relative_positions(mesh_list, time_stamps, margin=0.0):
    vtx_orig_pos = []

    pos_max = 0
    pos_min = 0    
    
    # Get original vtx positions from intermediate object
    for mesh in mesh_list:
        static_positions = get_unanimated_vertex_positions(mesh)
        vtx_orig_pos.extend(static_positions)

    #Compare the difference with the vertex positions during the animation of each frame.
    for frame in time_stamps:
        cmds.currentTime(frame)
        global_vtx_index = 0

        for mesh in mesh_list:
            vtx_count = cmds.polyEvaluate(mesh, vertex=True)
            for i in range(vtx_count):
                vtx = f"{mesh}.vtx[{i}]"
                pos = cmds.pointPosition(vtx, world=True)
                base = vtx_orig_pos[global_vtx_index]

                offset_x = pos[0] - base[0]
                offset_y = pos[1] - base[1]
                offset_z = pos[2] - base[2]

                pos_max = max(pos_max, offset_x, offset_y, offset_z)
                pos_min = min(pos_min, offset_x, offset_y, offset_z)

                global_vtx_index += 1    
    
    pos_max += margin
    pos_min -= margin
     
    return pos_min, pos_max

""" Returns min and max of relative normals """
def get_min_max_of_relative_normals(mesh_list, time_stamps, margin=0.0):
    normal_max = [1.0, 1.0, 1.0]
    normal_min = [-1.0, -1.0, -1.0]
    
    #Compare the difference with the vertex positions during the animation of each frame.
    for frame in time_stamps:
        cmds.currentTime(frame)

        for mesh in mesh_list:
            vtx_count = cmds.polyEvaluate(mesh, vertex=True)
            for i in range(vtx_count):
                vtx = f"{mesh}.vtx[{i}]"
                normal = cmds.polyNormalPerVertex(vtx, query=True, xyz=True)
                if normal:
                    nx, ny, nz = normal[:3]
                    normal_min[0] = min(normal_min[0], nx)
                    normal_min[1] = min(normal_min[1], ny)
                    normal_min[2] = min(normal_min[2], nz)
                    normal_max[0] = max(normal_max[0], nx)
                    normal_max[1] = max(normal_max[1], ny)
                    normal_max[2] = max(normal_max[2], nz)

    # 3軸それぞれに margin を加える
    return [v - margin for v in normal_min], [v + margin for v in normal_max]


""" Returns a list with appended and scaled vertex positions relative to first frame """
def append_vertex_positions_float32(mesh_list, time_stamps, scale_min, scale_max, progress_fn=None):
    """
    Returns a list of vertex position offsets (relative to the bind pose),
    scaled between scale_min and scale_max, and stored as flat float32 values.
    Output format: [X, Y, Z, 1.0,  X, Y, Z, 1.0,  ...] (per vertex per frame)
    """
    output_list = []
    original_pos_list = []

    # Get unanimated positions from intermediate object
    for mesh in mesh_list:
        original_pos_list.extend(get_unanimated_vertex_positions(mesh))
    
    total_frames = len(time_stamps)
    
    # Loop through each frame
    for i, frame in enumerate(time_stamps):
        cmds.currentTime(frame)
        global_vtx_index = 0

        for mesh in mesh_list:
            vtx_count = cmds.polyEvaluate(mesh, vertex=True)
            for j in range(vtx_count):
                vtx = f"{mesh}.vtx[{j}]"
                current_pos = cmds.pointPosition(vtx, world=True)
                base_pos = original_pos_list[global_vtx_index]

                # Offset from base pose
                offset_x = current_pos[0] - base_pos[0]
                offset_y = current_pos[1] - base_pos[1]
                offset_z = current_pos[2] - base_pos[2]

                output_list.extend([offset_x, offset_y, offset_z, 1.0])
                global_vtx_index += 1
             
        if progress_fn:
            percent = int((i + 1) / total_frames * 50) 
            progress_fn(percent)
    
    return output_list

def get_min_max_of_relative_positions_per_axis(mesh_list, time_stamps, margin=0.0):
    vtx_orig_pos = []

    x_min = y_min = z_min = float("inf")
    x_max = y_max = z_max = float("-inf")
    
    for mesh in mesh_list:
        static_positions = get_unanimated_vertex_positions(mesh)
        vtx_orig_pos.extend(static_positions)

    for frame in time_stamps:
        cmds.currentTime(frame)
        global_vtx_index = 0

        for mesh in mesh_list:
            vtx_count = cmds.polyEvaluate(mesh, vertex=True)
            for i in range(vtx_count):
                vtx = f"{mesh}.vtx[{i}]"
                pos = cmds.pointPosition(vtx, world=True)
                base = vtx_orig_pos[global_vtx_index]

                offset = [pos[i] - base[i] for i in range(3)]
                
                x_min = min(x_min, offset[0])
                x_max = max(x_max, offset[0])
                y_min = min(y_min, offset[1])
                y_max = max(y_max, offset[1])
                z_min = min(z_min, offset[2])
                z_max = max(z_max, offset[2])

                global_vtx_index += 1

    return (
        [x_min - margin, y_min - margin, z_min - margin],
        [x_max + margin, y_max + margin, z_max + margin]
    )


""" Returns a list with appended and scaled vertex normalz """
def append_normals_float32(mesh_list, time_stamps, scale_min, scale_max, progress_fn=None):
    output_list = []

    total_frames = len(time_stamps)
    
    """ Go through every frame """   
    first_frame = int(time_stamps[0])
    last_frame = int(time_stamps[-1])+1
    for i, frame in enumerate(time_stamps):
        cmds.currentTime(frame)
        for mesh in mesh_list:   
            vtx_count = cmds.polyEvaluate(mesh, vertex=True)
            for j in range(vtx_count):
                vtx = f"{mesh}.vtx[{j}]"
                normal = cmds.polyNormalPerVertex(vtx, query=True, xyz=True)
                if normal:
                    nx, ny, nz = normal[:3]
                else:
                    nx, ny, nz = 0.0, 0.0, 1.0

                # Dynamic scaling (different min/max per channel)
                norm_x = remap(scale_min[0], scale_max[0], 0.0, 1.0, nx)
                norm_y = remap(scale_min[1], scale_max[1], 0.0, 1.0, ny)
                norm_z = remap(scale_min[2], scale_max[2], 0.0, 1.0, nz)

                output_list.extend([norm_x, norm_y, norm_z, 1.0])  
            
            if progress_fn:
                percent = 50 + int((i + 1) / total_frames * 50) 
                progress_fn(percent)
                        
    return output_list

def save_float32_exr(buffer_list, width, height, save_path):
    import OpenEXR
    import Imath
    import numpy as np

    array = np.array(buffer_list, dtype=np.float32).reshape((height, width, 4))

    header = OpenEXR.Header(width, height)
    FLOAT = Imath.PixelType(Imath.PixelType.FLOAT)
    header['channels'] = {
        'R': Imath.Channel(FLOAT),
        'G': Imath.Channel(FLOAT),
        'B': Imath.Channel(FLOAT),
        'A': Imath.Channel(FLOAT)
    }

    r = array[:, :, 0].astype(np.float32).tobytes()
    g = array[:, :, 1].astype(np.float32).tobytes()
    b = array[:, :, 2].astype(np.float32).tobytes()
    a = array[:, :, 3].astype(np.float32).tobytes()

    out = OpenEXR.OutputFile(save_path, header)
    out.writePixels({'R': r, 'G': g, 'B': b, 'A': a})
    out.close()
    print(f"[Success] EXR file saved to: {save_path}")

#----------------------------------------------------------------
#----------------------------------------------------------------
""" Main program """
#----------------------------------------------------------------
#----------------------------------------------------------------
def make_dat_texture(output_dir=None, base_filename="output", progress_fn=None):
    if output_dir is None:
        output_dir = "C:/Textures/VAT/"

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    print("Start generating VAT...")
    print()
    start_time = time.time() 
    
    print("Collecting information...")

    mesh_list = []
    if (Selected_Meshes):
        mesh_list = get_list_of_selected_meshes()
    else:
        mesh_list = get_list_of_all_meshes()
    
    if len(mesh_list) != 1:
        cmds.error("Please select exactly one mesh.")
    
    nr_of_vtx = sum(cmds.polyEvaluate(m, vertex=True) for m in mesh_list)

    time_min = int(cmds.playbackOptions(q=True, min=True))
    time_max = int(cmds.playbackOptions(q=True, max=True))
    frame_range = list(range(time_min, time_max + 1))
    nr_of_frames = len(frame_range)
    
    fps = demystify(cmds.currentUnit(query=True, time=True))

    """ Derive next power of 2 to get width and height of texture """
    buffer_width = nr_of_vtx
    buffer_height = nr_of_frames
    
#-----------------------------------------------------------------------
    """ Get min & max position relative to first frame for normalize vertex positions with padding """
    print("Getting min and max positions for optimized scaling...")
    #scale_min, scale_max = get_min_max_of_relative_positions(mesh_list, frame_range, 0.1)
    scale_min, scale_max = get_min_max_of_relative_positions_per_axis(mesh_list, frame_range, 0.1)

#-----------------------------------------------------------------------
    # 頂点位置バッファの取得
    print("Appending vertex positions...")
    position_buffer = append_vertex_positions_float32(mesh_list, frame_range, scale_min, scale_max, progress_fn=progress_fn)

    # 法線バッファの取得
    print("Appending normals...")
    normal_min, normal_max = get_min_max_of_relative_normals(mesh_list, frame_range, 0.0)
    normal_buffer = append_normals_float32(mesh_list, frame_range, normal_min, normal_max, progress_fn=progress_fn)


#------------------------------------------
    """ Write data to file in EXR format """

    print("--- Analiiiizing ---")
    print("Buffer width :", buffer_width)
    print("Buffer height:", buffer_height)
    print("no of VTXs   :", nr_of_vtx)
    print("no of frames :", nr_of_frames)
    print("fps          :", fps)
    print("Scale_min    :", scale_min)
    print("Scale_max    :", scale_max)
    print()
    print("--- List lengths ---")
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    scene_name = cmds.file(q=True, sn=True, shortName=True).split('.')[0]

    #save position EXR
    pos_path = os.path.join(output_dir, base_filename + "_position.exr")
    save_float32_exr(position_buffer, buffer_width, nr_of_frames, pos_path)
    print("Position texture saved to:", pos_path)

    #save normal EXR
    nor_path = os.path.join(output_dir, base_filename + "_normal.exr")
    save_float32_exr(normal_buffer, buffer_width, nr_of_frames, nor_path)
    print("Normal texture saved to:", nor_path)
    
    elapsedTime = time.time() - start_time
    if (elapsedTime < 1) : sec = "of a second!!"
    if (elapsedTime == 1) : sec = "second!!"
    if (elapsedTime > 1) : sec = "seconds!! CALL YOUR LOCAL OPTIMIZER - 555-345345"
    print("It'sa done!! everything took just", elapsedTime, sec)