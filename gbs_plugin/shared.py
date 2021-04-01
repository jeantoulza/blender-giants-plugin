import struct
from typing import List
import math
import os
import tempfile
import bpy

GBS_VERSION = 0xaa0100be
GBSFlagNormals = 0x0001
GBSFlagUVs = 0x0002
GBSFlagRGBs = 0x0004
GBSFlagCalcNormals = 0x0008
GBSFlagMaxLit = (1 << 31)


def read_int(fp):
    return struct.unpack("<L", fp.read(4))[0]


def read_byte(fp):
    return struct.unpack("<B", fp.read(1))[0]


def read_float(fp):
    return struct.unpack("<f", fp.read(4))[0]


def read_short(fp):
    return struct.unpack("<H", fp.read(2))[0]


def read_string(fp, size):
    return read_bytes(fp, size).decode("utf8").replace("\x00", "")


def read_bytes(fp, size):
    return bytes(struct.unpack('<' + str(size) + 'B', fp.read(size)))


def read_string_until_none(fp) -> str:
    s = ""
    c = read_byte(fp)
    while c != 0x00:
        s += chr(c)
        c = read_byte(fp)
    return s


def decompress(compressed_bytes, original_size: int):
    i = 0
    j = 0
    dec_byte = 0
    dec_bits = 8
    buff_start = 0xFEE

    res = bytearray(original_size)

    if original_size == 0:
        return res

    while j < original_size:
        if dec_bits == 8:
            dec_byte = compressed_bytes[i]
            i += 1
            dec_bits = 0
        if (dec_byte >> dec_bits & 1) == 0:
            dec_pos = ((compressed_bytes[i] + (
                    (compressed_bytes[i + 1] & 0xF0) << 4) - buff_start - j) & 0xFFF) - 0x1000 + j
            dec_len = (compressed_bytes[i + 1] & 0xF) + 3
            i += 2
            while dec_len > 0:
                if dec_pos >= 0:
                    res[j] = res[dec_pos]
                else:
                    res[j] = 32
                j += 1
                dec_pos += 1
                dec_len -= 1
        else:
            res[j] = compressed_bytes[i]
            i += 1
            j += 1
        dec_bits += 1
    return res


class Vec2:
    def __init__(self, x=0.0, y=0.0):
        self.x = x
        self.y = y

    def __str__(self):
        return "[%s,%s]" % (self.x, self.y)


class Vec3:
    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x = x
        self.y = y
        self.z = z

    def __add__(self, other):
        return Vec3(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other):
        return self + -other

    def __radd__(self, other):
        return Vec3(self.x + other.x, self.y + other.y, self.z + other.z)

    def __mul__(self, scalar):
        return Vec3(self.x * scalar, self.y * scalar, self.z * scalar)

    def __rmul__(self, scalar):
        return Vec3(self.x * scalar, self.y * scalar, self.z * scalar)

    def __neg__(self):
        return Vec3(-self.x, -self.y, -self.z)

    def __pos__(self):
        return Vec3(self.x, self.y, self.z)

    def __xor__(self, other):
        cx = self.y * other.z - self.z * other.y
        cy = self.z * other.x - self.x * other.z
        cz = self.x * other.y - self.y * other.x
        return Vec3(cx, cy, cz)

    def cross(self, other):
        return self ^ other

    def normalize(self):
        w = math.sqrt(self.x ** 2 + self.y ** 2 + self.z ** 2)
        if w == 0:
            return Vec3()
        else:
            return Vec3(self.x / w, self.y / w, self.z / w)

    def __str__(self):
        return "[%s,%s,%s]" % (self.x, self.y, self.z)


class VecRGB:
    def __init__(self, r=0, g=0, b=0):
        self.r = r
        self.g = g
        self.b = b

    def __str__(self):
        return "[%s,%s,%s]" % (self.r, self.g, self.b)


def cross(v1: Vec3, v2: Vec3):
    return v1.cross(v2)


def resize(li: List, t, num):
    li.clear()
    for i in range(num):
        li.append(t())


class FileMaxObj:
    def __init__(self):
        self.vstart: int = 0
        self.vcount: int = 0
        self.nstart: int = 0
        self.ncount: int = 0
        self.noffset: int = 0


class MaxObj(FileMaxObj):
    def __init__(self):
        super().__init__()
        self.fstart: int = 0
        self.fcount: int = 0
        self.sostart: int = 0
        self.socount: int = 0


class SubObject:
    def __init__(self):
        self.objname: str = ""
        self.maxobjindex: int = 0
        self.ntris: int = 0  # count of tridata (including preceding 'count' short)
        self.totaltris: int = 0
        self.tridata: List[int] = []  # unsigned short
        self.verticeref_start: int = 0
        self.verticeref_count: int = 0
        self.texname: str = ""
        self.bumptexture: str = ""
        self.falloff: float = 0
        self.blend: float = 0
        self.flags: int = 0
        self.emissive: int = 0
        self.ambient: int = 0
        self.diffuse: int = 0
        self.specular: int = 0
        self.power: int = 0


class UV:
    def __init__(self, u: float = 0, v: float = 0):
        self.u: float = u
        self.v: float = v


class GbsData:
    def __init__(self):
        self.name = ""
        self.optionsflags: int = 0
        self.nndefs: int = 0
        self.num_normals: int = 0
        self.normals: List[int] = []  # word
        self.indexed_normals: List[int] = []  # unsigned short
        self.num_vertices: int = 0
        self.vertices: List[Vec3] = []
        self.nsobjs: int = 0
        self.nmobjs: int = 0
        self.indexed_vertices: List[int] = []  # unsigned short
        self.vertrgb: List[VecRGB] = []
        self.nverts: int = 0
        self.vertuv: List[UV] = []
        self.MaxObjs: List[MaxObj] = []
        self.SubObjs: List[SubObject] = []

    def read(self, file):
        debug = True
        self.name = os.path.basename(file)
        with open(file, "rb") as fp:
            version_header = read_int(fp)
            if version_header != GBS_VERSION:
                raise Exception("File does not appear to be a GBS file.")

            self.optionsflags = read_int(fp)
            self.num_vertices = read_int(fp)
            resize(self.vertices, Vec3, self.num_vertices)
            for i in range(self.num_vertices):
                self.vertices[i].x = read_float(fp)
                self.vertices[i].y = read_float(fp)
                self.vertices[i].z = read_float(fp)

            if self.optionsflags & GBSFlagNormals:
                self.nndefs = read_int(fp)
                self.num_normals = read_int(fp)
                resize(self.normals, int, self.num_normals)
                for i in range(self.num_normals):
                    self.normals[i] = read_short(fp)

            self.nverts = read_int(fp)
            if debug: print(
                "NVERTS=%s, NUMVERTICES=%s, options=%s" % (self.nverts, self.num_vertices, self.optionsflags))
            resize(self.indexed_vertices, int, self.nverts)
            for i in range(self.nverts):
                self.indexed_vertices[i] = read_short(fp)
            if debug: print(self.indexed_vertices)

            if self.optionsflags & GBSFlagNormals:
                resize(self.indexed_normals, int, self.nverts)
                for i in range(self.nverts):
                    self.indexed_normals[i] = read_short(fp)

            if self.optionsflags & GBSFlagUVs:
                resize(self.vertuv, UV, self.nverts)
                if debug: print("Read %s UV" % self.nverts)
                for i in range(self.nverts):
                    self.vertuv[i].u = read_float(fp)
                    self.vertuv[i].v = read_float(fp) * -1

            if self.optionsflags & GBSFlagRGBs:
                resize(self.vertrgb, VecRGB, self.nverts)
                if debug: print("Read %s RGB" % self.nverts)
                for i in range(self.nverts):
                    self.vertrgb[i].r = read_byte(fp)
                    self.vertrgb[i].g = read_byte(fp)
                    self.vertrgb[i].b = read_byte(fp)

            # Get number of objects
            self.nmobjs = read_int(fp)
            if debug: print("NMOBJS = %s" % self.nmobjs)
            resize(self.MaxObjs, MaxObj, self.nmobjs)
            for maxobj in self.MaxObjs:
                print("Processing new maxobj")
                fileMaxObj = FileMaxObj()
                fileMaxObj.vstart = read_int(fp)
                fileMaxObj.vcount = read_int(fp)
                fileMaxObj.nstart = read_int(fp)
                fileMaxObj.ncount = read_int(fp)
                fileMaxObj.noffset = read_int(fp)
                print("vstart=%s vcount=%s nstart=%s ncount=%s noffset=%s" % (
                fileMaxObj.vstart, fileMaxObj.vcount, fileMaxObj.nstart, fileMaxObj.ncount, fileMaxObj.noffset))
                maxobj.vstart = fileMaxObj.vstart
                maxobj.vcount = fileMaxObj.vcount
                maxobj.nstart = fileMaxObj.nstart
                maxobj.ncount = fileMaxObj.ncount
                maxobj.noffset = fileMaxObj.noffset
                maxobj.fstart = 0
                maxobj.fcount = 0
                maxobj.sostart = 0
                maxobj.socount = 0

            # verify max obj
            nmcount = 0
            for maxobj in self.MaxObjs:
                nmcount += maxobj.vcount
            assert nmcount == self.num_vertices

            self.nsobjs = read_int(fp)
            print("Subobject count: %s" % self.nsobjs)
            resize(self.SubObjs, SubObject, self.nsobjs)
            num_faces = 0
            len_tridata = 0
            for ns in range(self.nsobjs):
                if debug: print("Processing subobj %s" % ns)
                object = self.SubObjs[ns]
                object.objname = read_string(fp, 32)
                object.maxobjindex = read_int(fp)
                object.totaltris = read_int(fp)
                if debug: print("read %s totaltris" % object.totaltris)
                num_faces += object.totaltris
                object.ntris = read_int(fp)

                assert ((object.ntris - 1) / 3 == object.totaltris)

                resize(object.tridata, int, object.ntris + 1)
                if debug: print("read gbs: totaltris: %s, tridata is %s long, ntris: %s" % (
                object.totaltris, len(object.tridata), object.ntris))
                len_tridata += object.ntris + 1
                for i in range(object.ntris):
                    object.tridata[i] = read_short(fp)

                # if debug: print("tridata: %s" % object.tridata)

                object.verticeref_start = read_int(fp)
                object.verticeref_count = read_int(fp)
                if self.optionsflags & GBSFlagUVs:
                    object.texname = read_string(fp, 32)
                    object.bumptexture = read_string(fp, 32)

                object.falloff = read_float(fp)
                if self.optionsflags & GBSFlagRGBs:
                    object.blend = read_float(fp)

                object.flags = read_int(fp)
                object.emissive = read_int(fp)
                object.ambient = read_int(fp)
                object.diffuse = read_int(fp)
                object.specular = read_int(fp)
                object.power = read_float(fp)
                if debug: print(
                    "%s (%s) falloff: %s, blend: %s, flags:%s, emissive: %s, ambiant: %s, diffuse: %s, specular: %s, power: %s" % (
                    object.objname, object.texname, object.falloff, object.blend, object.flags, object.emissive,
                    object.ambient, object.diffuse, object.specular, object.power))

                maxobj = self.MaxObjs[object.maxobjindex]
                maxobj.fcount += object.totaltris
                if not maxobj.socount:
                    maxobj.socount = ns

                maxobj.socount += 1
            if debug: print("read num_faces: %s, len_tridata: %s" % (num_faces, len_tridata))

    @staticmethod
    def evaluate_tridata(tridata, tri_idx, count):
        if count == 0:
            count = tridata[0]
            if count == 0:
                return False
            tri_idx = 0
        v1 = tridata[tri_idx + 1]
        v2 = tridata[tri_idx + 2]
        v3 = tridata[tri_idx + 3]
        tri_idx += 3

        count -= 1
        if count < 0:
            count = 0xffff  # max unsigned short
        if count == 0:
            tridata = tridata[tridata[0] * 3 + 1:]
        return tridata, tri_idx, count, v1, v2, v3

    def generate_normals(self):
        normals: List[Vec3] = []
        resize(normals, Vec3, self.num_vertices)
        for subobj_i in range(len(self.SubObjs)):
            subobj = self.SubObjs[subobj_i]
            tridata = subobj.tridata
            values = self.evaluate_tridata(tridata, -1, 0)
            while values:
                tridata, tri_idx, count, v1, v2, v3 = values
                try:
                    p = cross(self.vertices[self.indexed_vertices[v2]] - self.vertices[self.indexed_vertices[v1]],
                              self.vertices[self.indexed_vertices[v3]] - self.vertices[self.indexed_vertices[v1]])
                except Exception as e:
                    raise e
                normals[self.indexed_vertices[v1]] += p
                normals[self.indexed_vertices[v2]] += p
                normals[self.indexed_vertices[v3]] += p
                values = self.evaluate_tridata(tridata, tri_idx, count)

        for i in range(len(normals)):
            normals[i] = normals[i].normalize()
        return normals


def find_and_extract_texture(texture_filename, objname, giantspath):
    game_folder = giantspath
    game_folder = game_folder + "/Bin"

    for gzp_filename in os.listdir(game_folder):
        if not gzp_filename.endswith(".gzp"):
            continue

        gzp_fp = open(game_folder + "/" + gzp_filename, "rb")

        checksum = read_int(gzp_fp)
        if checksum != 0x6608F101:
            raise Exception("Invalid GZP checksum")

        meta_info_offset = read_int(gzp_fp)

        gzp_fp.seek(meta_info_offset)
        unk = read_int(gzp_fp)
        entries_count = read_int(gzp_fp)

        if entries_count == 0:
            continue

        for index in range(entries_count):
            compressed_size = read_int(gzp_fp)
            original_size = read_int(gzp_fp)
            file_time = read_int(gzp_fp)
            content_offset = read_int(gzp_fp) + 16
            compression = read_byte(gzp_fp)  # compression: 1 if compressed else 0
            name_length = read_byte(gzp_fp)
            name = read_bytes(gzp_fp, name_length).decode("utf8").strip('\x00')

            texture_name = name.lower()
            if not texture_name.endswith(".tga"):
                continue

            texture_name = texture_name[0:-4]
            if texture_name != texture_filename.lower():
                continue

            curr_pos = gzp_fp.tell()
            gzp_fp.seek(content_offset)
            buffer = gzp_fp.read(compressed_size)
            gzp_fp.seek(curr_pos)

            if compression == 1:
                buffer = decompress(buffer, original_size)

            fd, filename = tempfile.mkstemp(suffix=".tga", prefix=objname, dir=None, text=False)
            with open(filename, "wb") as entry_fp:
                entry_fp.write(buffer)

            return filename
    return None


def material_from_file(filename, matname):
    image = bpy.data.images.load(filename, check_existing=True)
    texture = bpy.data.textures.new(matname, type='IMAGE')
    texture.image = image

    mat = bpy.data.materials.new(matname)
    mat.preview_render_type = 'FLAT'
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    texImage = mat.node_tree.nodes.new('ShaderNodeTexImage')
    texImage.image = image
    mat.node_tree.links.new(bsdf.inputs['Base Color'], texImage.outputs['Color'])
    return mat
