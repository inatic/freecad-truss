import FreeCAD
import Part
from Truss import BeamGui

class Beam():
    def __init__(self, object, line, width, height):

        object.Proxy = self
        object.addProperty('App::PropertyString', 'Description', 'Base', 'Beam description').Description = "This is a beam"
        object.addProperty('App::PropertyString', 'Type', 'Base', 'Object type').Type = "Beam"
        object.addProperty('App::PropertyLength', 'Length', 'Dimensions', 'Box length').Length
        object.addProperty('App::PropertyLength', 'Width', 'Dimensions', 'Box width').Width
        object.addProperty('App::PropertyLength', 'Height', 'Dimensions', 'Box height').Height

        object.Length = line.Length
        object.Width = width
        object.Height = height

    def execute(self, object):
        """
        Called on document recompute
        """

        mybeam = Part.makeBox(object.Length, object.Width, object.Height)
        object.Shape = mybeam

def test():
    '''
    Create a simple beam, for testing
    '''

    document = FreeCAD.ActiveDocument
    if not document:
        document = FreeCAD.newDocument()
    
    v0 = FreeCAD.Vector(-500, 50, 50)
    v1 = FreeCAD.Vector( 500, 50, 50)
    line = Part.makeLine(v0, v1)
    
    beamObject = document.addObject("Part::FeaturePython", "TestBeam")
    width = 100
    height = 100
    Beam(beamObject, line, width, height)
    document.recompute()
    BeamGui.ViewProviderBox(beamObject.ViewObject)
