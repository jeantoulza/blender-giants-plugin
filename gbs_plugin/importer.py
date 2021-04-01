from .shared import *


def imp_gbs(gbspath, giantspath):
    path = gbspath
    game_folder = giantspath
    gbs = GbsData()
    gbs.read(path)
    name = os.path.splitext(os.path.basename(path))[0]

    map_collection = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(map_collection)

    verts = []
    for index in gbs.indexed_vertices:
        v = gbs.vertices[index]
        vert = (v.x, v.y, v.z)
        verts.append(vert)

    for subobj in gbs.SubObjs:
        fool = 0
        uvs = []

        mesh = bpy.data.meshes.new(subobj.objname)
        obj = bpy.data.objects.new(mesh.name, mesh)
        faces = []

        curr_index = 0
        print(subobj.tridata)
        while curr_index < len(subobj.tridata) - 1:
            num_tris = subobj.tridata[curr_index]
            for tri_num in range(num_tris):
                curr_face = []
                for k in range(3):
                    vert_index = subobj.tridata[curr_index + 1 + tri_num * 3 + k]
                    curr_face.append(vert_index)

                    u = gbs.vertuv[vert_index].u
                    v = gbs.vertuv[vert_index].v
                    uv = (u, v)
                    uvs.append(uv)

                faces.append(curr_face)
            curr_index = num_tris * 3 + 1

        mesh.from_pydata(verts, [], faces)
        map_collection.objects.link(obj)

        # Uvs
        uv_layer = mesh.uv_layers.new(name="UV")
        mesh.uv_layers.active = uv_layer

        for i in range(len(uvs)):
            uv_layer.data[i].uv = uvs[i]

        tmpfilename = find_and_extract_texture(subobj.texname, name, game_folder)
        mat = material_from_file(tmpfilename, subobj.texname)
        if obj.data.materials:
            # assign to 1st material slot
            obj.data.materials[0] = mat
        else:
            # no slots
            obj.data.materials.append(mat)