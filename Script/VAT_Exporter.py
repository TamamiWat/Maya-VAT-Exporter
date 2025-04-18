# import pymel.core as pm
# from PIL import Image
# from PIL import ImagePalette
# from PIL import ImageShow
import os
import struct
import time
import math
import numpy as np
import imageio.v2 as imageio
import VAT_Exporter_UI as ui
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

""" Returns a list of keyframes from objects in list """
def get_list_of_keyframes(object_list):
    #get range of time slider
    time_min = cmds.playbackOptions(q=True, min=True)
    time_max = cmds.playbackOptions(q=True, max=True)

    #get keyframes
    keyframes=cmds.keyframe(object_list, time=(time_min, time_max), query=True)
    if not keyframes:
        return []
    
    unique_keys = sorted(set(keyframes))
    return unique_keys
    
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
    
""" Returns a list of all the vertecies positions from a list of meshes """
def get_list_of_vertex_positions(mesh_list):
    vtx_pos = []
    for mesh_index, mesh in enumerate(mesh_list):   
        for vtx_index, vtx in enumerate(mesh.vtx):
            pos = vtx.getPosition(space="world")
            vtx_pos.append(pos)
    return vtx_pos    


""" Returns the next n^2 of n """
def get_next_power_of_2(n):
    if n == 0:
        return 1
    if n & (n - 1) == 0:
        return n
    while n & (n - 1) > 0:
        n &= (n - 1)
    return n << 1

    
""" Write "global" vertex index in all meshes vertecies in mesh_list to the red and green vertex color channels """    
#use 32bit
def write_vertex_index_to_vertex_color(mesh_list):
    global_vtx_index = 0
    cmds.currentTime(0)

    for mesh in mesh_list:
        vertex_count = cmds.polyEvaluate(mesh, vertex=True)

        for i in range(vertex_count):
            r_byte, g_byte, b_byte, a_byte = (global_vtx_index & 0xFFFFFFFF).to_bytes(4, 'big')

            r = remap(0, 255, 0, 1, r_byte)
            g = remap(0, 255, 0, 1, g_byte)
            b = remap(0, 255, 0, 1, b_byte)
            a = remap(0, 255, 0, 1, a_byte)

            vtx_name = f"{mesh}.vtx[{i}]"

            cmds.polyColorPerVertex(vtx_name, rgb=(r, g, b), a=a, cdo=True)

            global_vtx_index += 1          

"""" Returns vertex positions of intermediate object """
def get_unanimated_vertex_positions(mesh):
    shapes = cmds.listRelatives(mesh, shapes=True, fullPath=True) or []
    for shape in shapes:
        if cmds.getAttr(shape + ".intermediateObject"):
            intermediate_shape = shape
            break
    else:
        print(f"[Warning] No intermediate shape found for {mesh}")
        return []

    count = cmds.polyEvaluate(intermediate_shape, vertex=True)
    positions = []
    for i in range(count):
        vtx = f"{intermediate_shape}.vtx[{i}]"
        pos = cmds.pointPosition(vtx, world=True)
        positions.append(pos)
    return positions

"""" Returns vertex normals of intermediate object """
def get_ununimated_vertex_normals(mesh):
    shapes = cmds.listRelatives(mesh, shapes=True, fullPath=True) or []
    for shape in shapes:
        if cmds.getAttr(shape + ".intermediateObject"):
            intermediate_shape = shape
            break
    else:
        print(f"[Warning] No intermediate shape found for {mesh}")
        return []

    count = cmds.polyEvaluate(intermediate_shape, vertex=True)
    normals = []
    for i in range(count):
        vtx = f"{intermediate_shape}.vtx[{i}]"
        n = cmds.polyNormalPerVertex(vtx, query=True, xyz=True)
        normals.append(n[:3])  # First one normal vector
    return normals

""" Returns min and max of relative positions """
def get_min_max_of_relative_positions(mesh_list, time_stamps, margin):
    vtx_orig_pos = []

    pos_max = 0
    pos_min = 0    
    
    # Get original vtx positions from intermediate object
    for mesh in mesh_list:
        static_positions = get_unanimated_vertex_positions(mesh)
        vtx_orig_pos.extend(static_positions)

    #Compare the difference with the vertex positions during the animation of each frame.
    for frame in range(0,len(time_stamps)):
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

""" Returns a power of 2 header list """
# def create_header_list(number_of_frames, frame_rate, scale_min, scale_max, next_power_of_2):
#     header_list = []
    
#     """ Add no of frames to R channel of first pixel """    
#     header_list.append(number_of_frames)
    
#     """ Add Frame Rate to G channel of first pixel """
#     header_list.append(frame_rate)
       
    
#     """ Padd B & A channels in first pixel """    
#     header_list.append(255)     
#     header_list.append(255)
    
#     """ Add scale_min and scale_max to second and third pixel """ 
#     minBytes = bytearray(struct.pack("f", scale_min))
#     maxBytes = bytearray(struct.pack("f", scale_max))  
    
#     header_list.append(minBytes[0])
#     header_list.append(minBytes[1])
#     header_list.append(minBytes[2])            
#     header_list.append(minBytes[3])
    
#     header_list.append(maxBytes[0])
#     header_list.append(maxBytes[1])
#     header_list.append(maxBytes[2])            
#     header_list.append(maxBytes[3])    
    
#     """ Padd pixels if needed """
#     padding_range = next_power_of_2 - int(len(header_list)/4)    
#     for i in range(padding_range):
#         header_list.append(0)
#         header_list.append(255)
#         header_list.append(255)
#         header_list.append(0)
    
#     return header_list

# def make_diff():
#     my_mesh = pm.ls(sl = True)
#     print(my_mesh)
#     diff = 0.007229555950445166
#     pos_orig = []
#     pos_new = [0,0,0]
#     for mesh_index, mesh in enumerate(my_mesh):  
#         print(mesh_index, mesh) 
#         for vtx_index, vtx in enumerate(mesh.vtx):
#             print(vtx_index, vtx)
#             pos = vtx.getPosition(space="world")
            
#             print(pos)
#             if (vtx_index == 0): 
#                 pos_orig = vtx.getPosition(space="world")
#                 print("orig :",pos_orig)
#             if (vtx_index == 1):
#                 print("Vertex 1")
#                 pos_new[X] = pos_orig[X] + diff
#                 pos_new[Y] = pos_orig[Y] + diff
#                 pos_new[Z] = pos_orig[Z] + diff
#                 vtx.setPosition(pos_new, space='world')
                
#             if (vtx_index == 2):
#                 print("Vertex 2")
#                 pos_new[X] = pos_orig[X] + diff
#                 pos_new[Y] = pos_orig[Y] + diff
#                 pos_new[Z] = pos_orig[Z] + diff
#                 vtx.setPosition(pos_new, space='world')
                
#             if (vtx_index == 3):
#                 print("Vertex 3")
#                 vtx.setPosition(pos_orig, space='world')

       
# def append_vertex_positions_and_normals(header_list, mesh_list, time_stamps, scale_min, scale_max):

#     header_length = int(len(header_list)/4)
#     output_pos_list = []
#     output_normal_list = []
#     original_pos_list = []
    
#     pm.currentTime(time_stamps[0])
    
#     """ Original vtx positions """
#     for mesh_index, mesh in enumerate(mesh_list):   
#         for vtx_index, vtx in enumerate(mesh.vtx):
#             pos = vtx.getPosition(space="world")
#             original_pos_list.append(pos)  
    
#     """ Go through every frame """
#     first_frame = int(time_stamps[0])
#     last_frame = int(time_stamps[-1])+1
#     for frame in range(first_frame ,last_frame):
#         global_vtx_index = 0
#         pm.currentTime(frame)
#         for mesh_index, mesh in enumerate(mesh_list):         
#             for vtx_index, vtx in enumerate(mesh.vtx):  
            
#                 """ Get new position, calculate position difference and append scaled value """  
#                 pos = vtx.getPosition(space="world") 

#                 pos[X] = remap(scale_min, scale_max, 0, 255, pos[X] - original_pos_list[global_vtx_index][X])
#                 pos[Y] = remap(scale_min, scale_max, 0, 255, pos[Y] - original_pos_list[global_vtx_index][Y])
#                 pos[Z] = remap(scale_min, scale_max, 0, 255, pos[Z] - original_pos_list[global_vtx_index][Z])
                
#                 output_pos_list.append(int(round(pos[X])))
#                 output_pos_list.append(int(round(pos[Y])))
#                 output_pos_list.append(int(round(pos[Z])))           
#                 output_pos_list.append(255)                           
                
#                 """ Get vtx normal and append to next pixel """
#                 myNormal = vtx.getNormal('world')
#                 normalX = int(remap(-1, 1, 0, 65535, myNormal[X]))
#                 normalY = int(remap(-1, 1, 0, 65535, myNormal[Y]))
                                                                          
#                 """ X-Component """
#                 y1, y2, y3, y4 = (normalX & 0xFFFFFFFF).to_bytes(4, 'big')
#                 output_normal_list.append(y3)
#                 output_normal_list.append(y4)
                               
#                 """ Y-Component """
#                 y1, y2, y3, y4 = (normalY & 0xFFFFFFFF).to_bytes(4, 'big')
#                 output_normal_list.append(y3)
#                 output_normal_list.append(y4)

#                 global_vtx_index += 1
        
       
#         padding_range = int(header_length - global_vtx_index)
#         if (header_length > global_vtx_index):
#             for i in range(padding_range):
#                 output_pos_list.append(255)
#                 output_pos_list.append(255)
#                 output_pos_list.append(0)
#                 output_pos_list.append(0) 
#                 output_normal_list.append(255)
#                 output_normal_list.append(255)
#                 output_normal_list.append(0)
#                 output_normal_list.append(0)
       
#     return header_list + output_pos_list + output_normal_list               


""" Returns a list with appended and scaled vertex positions relative to first frame """
def append_vertex_positons(mesh_list, time_stamps, scale_min, scale_max):

    output_list = []
    original_pos_list = []
    
    pm.currentTime(time_stamps[0])
    
    """ Original vtx positions """
    for mesh_index, mesh in enumerate(mesh_list):   
        for vtx_index, vtx in enumerate(mesh.vtx):
            pos = vtx.getPosition(space="world")
            original_pos_list.append(pos)  
    
    """ Go through every frame """
    
    first_frame = int(time_stamps[0])
    last_frame = int(time_stamps[-1])+1
    for frame in range(first_frame ,last_frame):
        global_vtx_index = 0
        pm.currentTime(frame)
        for mesh_index, mesh in enumerate(mesh_list):         
            for vtx_index, vtx in enumerate(mesh.vtx):  
            
                """ Get new position, calculate position difference and append scaled value """  
                pos = vtx.getPosition(space="world") 
                pos[0] = remap(scale_min, scale_max, 0, 255, pos[X] - original_pos_list[global_vtx_index][X])
                pos[1] = remap(scale_min, scale_max, 0, 255, pos[Y] - original_pos_list[global_vtx_index][Y])
                pos[2] = remap(scale_min, scale_max, 0, 255, pos[Z] - original_pos_list[global_vtx_index][Z])
    
                output_list.append(int(round(pos[X])))
                output_list.append(int(round(pos[Y])))
                output_list.append(int(round(pos[Z])))            
                output_list.append(255)


                global_vtx_index += 1
             
    return output_list


""" Returns a list with appended and scaled vertex normalz """
def append_normals(mesh_list, time_stamps):
    output_list = []
    
    """ Go through every frame """   
    first_frame = int(time_stamps[0])
    last_frame = int(time_stamps[-1])+1
    for frame in range(first_frame ,last_frame):
        global_vtx_index = 0
        pm.currentTime(frame)
        for mesh_index, mesh in enumerate(mesh_list):         
            for vtx_index, vtx in enumerate(mesh.vtx):  
                
                """ Get vtx normal and append to next pixel """
                myNormal = vtx.getNormal('world')
                normalX = int(remap(-1, 1, 0, 65535, myNormal[X]))
                normalY = int(remap(-1, 1, 0, 65535, myNormal[Y]))
                                                                          
                """ X-Component """
                y1, y2, y3, y4 = (normalX & 0xFFFFFFFF).to_bytes(4, 'big')
                output_list.append(y3)
                output_list.append(y4)
                               
                """ Y-Component """
                y1, y2, y3, y4 = (normalY & 0xFFFFFFFF).to_bytes(4, 'big')
                output_list.append(y3)
                output_list.append(y4)

                global_vtx_index += 1
                    
    return output_list


""" Adds padding to end of list to get a power of 2 texture """
# def add_padding_to_eol(buffer_list, buffer_width, buffer_height):
#     output_list = []
    
#     len_buffer_list = len(buffer_list)/4
#     expected_len_buffer_list = buffer_width * buffer_height
#     missing_buffer_len = int(expected_len_buffer_list - len_buffer_list )

#     if (missing_buffer_len > 0):
#         for i in range(missing_buffer_len):
#             output_list.append(255)
#             output_list.append(0)
#             output_list.append(255)
#             output_list.append(0)     
        
#     return buffer_list + output_list

def save_float32_exr(buffer_list, width, height, save_path):
    # buffer_list : flat float values' list [R, G, B, A, R, G, B, A, ...]
    array = np.array(buffer_list, dtype=np.float32).reshape((height, width, 4))
    imageio.imwrite(save_path, array, format='EXR')

#----------------------------------------------------------------
#----------------------------------------------------------------
""" Main program """
#----------------------------------------------------------------
#----------------------------------------------------------------
def make_dat_texture():
    print("Let'sa GOOO!!")
    print()
    start_time = time.time() 
    
    print("Collecting information...")

    mesh_list = []
    if (Selected_Meshes):
        mesh_list = get_list_of_selected_meshes()
    else:
        mesh_list = get_list_of_all_meshes()
    
    keyframes = get_list_of_keyframes(mesh_list) 
    
    nr_of_vtx = len(get_list_of_vertex_positions(mesh_list))
 
    first_frame = int(keyframes[0])
    last_frame = int(keyframes[-1])
    nr_of_frames = last_frame - first_frame + 1
    
    fps = demystify(pm.currentUnit(query=True, time=True))

    """ Derive next power of 2 to get width and height of texture """
    buffer_width = get_next_power_of_2(nr_of_vtx) 
    buffer_height = get_next_power_of_2(nr_of_frames*2+1)
    

    
#-----------------------------------------------------------------------
    """ Write vertex index to every vertex of all meshes in list  """
    print("Writing vertex index to vertex colors...")
    write_vertex_index_to_vertex_color(mesh_list)
    
    
#-----------------------------------------------------------------------
    """ Get min & max position relative to first frame for normalize vertex positions with padding """
    print("Getting min and max positions for optimized scaling...")
    scale_min, scale_max = get_min_max_of_relative_positions(mesh_list, keyframes, 0.1)
    
    
#-----------------------------------------------------------------------
    # """ Create Header information """
    # print("Creating header...")
    # header_list = create_header_list(nr_of_frames, fps, scale_min, scale_max, buffer_width)

    
#-----------------------------------------------------------------------
    """ Loops through the vertices of all meshes and store difference in pos into new array """
    print("Appending vertex-positions and normals to buffert...")
    header_vertex_pos_normals_list = append_vertex_positions_and_normals(header_list, mesh_list, keyframes, scale_min, scale_max)
    #header_vertex_pos_list = append_vertex_positons(header_list, mesh_list, keyframes, scale_min, scale_max)
   
    
#-----------------------------------------------------------------------
    """ Loops through the vertices of all meshes and store difference in pos into new array """   
    #print("Appending vertex-normals to buffert...") 
    #header_vertex_pos_normals_list = append_normals(header_list, header_vertex_pos_list, mesh_list, keyframes)
    
    
#-----------------------------------------------------------------------
    """ Add padding to end of list """
    # print("Appending padding to end of buffert...")
    # header_vertex_pos_padding_list = add_padding_to_eol(header_vertex_pos_normals_list, buffer_width, buffer_height)
    
    
#-----------------------------------------------------------------------
    # 頂点位置バッファの取得
    print("Appending vertex positions...")
    position_buffer = append_vertex_positons(mesh_list, keyframes, scale_min, scale_max)

    # 法線バッファの取得
    print("Appending normals...")
    normal_buffer = append_normals(mesh_list, keyframes)


#------------------------------------------
    """ Write data to file in DDS format """
    
    
    
    print("--- Analiiiizing ---")
    print("Buffer width :", buffer_width)
    print("Buffer height:", buffer_height)
    print("no of VTXs   :", nr_of_vtx)
    print("no of frames :", nr_of_frames)
    print("fps          :", fps)
    print("Scale_min    :", scale_min)
    print("Scale_max    :", scale_max)
    print()
    print("--- List lenghts ---")
    
    header_len = len(header_list)/4
    print("Header list        :", str(header_len), "     Expected :", buffer_width)
    vtx_list = (len(header_vertex_pos_normals_list)/4) - header_len
    
    print("vertex pos list    :", str(vtx_list/2), "    Expected :", buffer_width*nr_of_frames)
    tot_len = len(header_vertex_pos_padding_list)/4
    
    print("Total with padding :", str(tot_len) , "    Expected :", buffer_width*buffer_height)
    print()
    
    
    IM_created = ImagePalette.ImagePalette(mode='RGBA', palette=header_vertex_pos_padding_list)
    IMTB = IM_created.tobytes()
    
    IMFB = Image.frombuffer("RGBA", (buffer_width, buffer_height), IMTB, decoder_name='raw')
    
    texturePath = "D:\Textures\Vats\\"
    textureName = pm.system.sceneName().split('/')[-1].split('.')[0]
    textureExtension = ".dds"
    texturePathName = texturePath + textureName + textureExtension
    
    """ Check if directory exist else create it then save the file """
    print("Saving dds...")
    if os.path.exists(texturePath):
        IMFB = IMFB.save(texturePathName)
        print("File saved to : ", texturePathName)
    else:
        os.makedirs(texturePath)
        if os.path.exists(texturePath):
            IMFB = IMFB.save(texturePathName)
            print("File saved to : ", texturePathName)
        else:
            print("dir fault")
    #-----------------------------------------------
    

    
    elapsedTime = time.time() - start_time
    if (elapsedTime < 1) : sec = "of a second!!"
    if (elapsedTime == 1) : sec = "second!!"
    if (elapsedTime > 1) : sec = "seconds!! CALL YOUR LOCAL OPTIMIZER - 555-345345"
    print("It'sa done!! everything took just", elapsedTime, sec)
    



