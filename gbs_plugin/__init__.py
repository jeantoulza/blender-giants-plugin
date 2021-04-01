# addon information
import bpy
from bpy.types import Operator, AddonPreferences
from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty
from .importer import imp_gbs
import time



bl_info = {
    "name": "Import Giants GBS format",
    "author": "Amazed#0001",
    "version": (1, 0),
    "blender": (2, 80, 0),
    "location": "File > Import > Giants GBS (.gbs)",
    "description": "Import static objects from Giants GBS files.",
    "category": "Import-Export",
}

class GBSPreferences(AddonPreferences):
    # this must match the addon name, use '__package__'
    # when defining this in a submodule of a python package.
    bl_idname = __name__

    game_path = StringProperty(
        name="Your Giants game folder",
        description="This is needed to extract textures",
        subtype='DIR_PATH'
    )

    def draw(self, context):
        layout = self.layout
        layout.label(text="GBS plugin preferences")
        layout.prop(self, "game_path")


# main code
class GBSImporter(bpy.types.Operator, ImportHelper):
    bl_idname       = "gbs_importer.gbs"
    bl_description  = "Import Giants model files (.gbs)"
    bl_label        = "Giants GBS Importer"
    bl_options      = {'REGISTER', 'UNDO'}

    filename_ext = ".gbs"
    filter_glob: StringProperty(
        default="*.gbs",
        options={'HIDDEN'},
        )

    filter_glob: StringProperty(
        default="*.gbs",
        options={'HIDDEN'},
    )

    def execute(self, context):
        user_preferences = context.preferences
        addon_prefs = user_preferences.addons[__name__].preferences

        time_start = time.time()

        game_path = addon_prefs.game_path

        if not game_path:
            raise Exception("Please set your Giants folder in the add-on preferences")
        imp_gbs(self.filepath, game_path)
        print("Elapsed time: %.2fs" % (time.time() - time_start))
        return {'FINISHED'}

classes = (
    GBSPreferences,
    GBSImporter
)

def menu_func(self, context):
    self.layout.operator(GBSImporter.bl_idname, text="Giants GBS (.gbs)")


def register():
    for c in classes:
        bpy.utils.register_class(c)

    bpy.types.TOPBAR_MT_file_import.append(menu_func)


def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(menu_func)

    for c in classes:
        bpy.utils.unregister_class(c)