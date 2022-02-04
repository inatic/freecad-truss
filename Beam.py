import FreeCAD
import Part
from Truss import BeamGui

class Beam():
    def __init__(self, object):

        object.Proxy = self
        object.addProperty('App::PropertyString', 'Description', 'Base', 'Beam description').Description = "This is a beam"
        object.addProperty('App::PropertyString', 'Type', 'Base', 'Object type').Type = "Beam"
        object.addProperty('App::PropertyLength', 'Length', 'Dimensions', 'Box length').Length = '200 cm'
        object.addProperty('App::PropertyLength', 'Width', 'Dimensions', 'Box width').Width = '10 cm'
        object.addProperty('App::PropertyLength', 'Height', 'Dimensions', 'Box height').Height = '10 cm'

    def execute(self, object):
        """
        Called on document recompute
        """

        mybeam = Part.makeBox(object.Length, object.Width, object.Height)
        object.Shape = mybeam

def test(objectName="myBeam"):
    """ Add a beam to a document, used for testing """

    document = FreeCAD.ActiveDocument
    if not document:
        document = FreeCAD.newDocument()

    beamObject = document.addObject("Part::FeaturePython", objectName)
    Beam(beamObject)
    document.recompute()
    BeamGui.ViewProviderBox(beamObject.ViewObject)

    return beamObject

