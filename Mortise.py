import FreeCAD
import Part
from Truss import MortiseGui
from Truss import PathAdaptive

class Mortise():
    """ Create a mortise and tenon joint"""
    def __init__(self, obj):

        obj.Proxy = self

        obj.addProperty('App::PropertyString', 'Description', 'Base', 'Joint description').Description = "Mortise and tenon joint"
        obj.addProperty('App::PropertyEnumeration', 'Type', 'Base', 'Joint type').Type = ["mortise","tenon"]
        obj.Type = "mortise"

        obj.addProperty('App::PropertyLength', 'StockWidth', 'Dimensions', 'Stock width').StockWidth = '102 mm'
        obj.addProperty('App::PropertyLength', 'StockHeight', 'Dimensions', 'Stock length').StockHeight = '102 mm'
        obj.addProperty('App::PropertyLength', 'MortiseWidth', 'Dimensions', 'Mortise width').MortiseWidth = '30 mm'
        obj.addProperty('App::PropertyLength', 'MortiseLength', 'Dimensions', 'Mortise length').MortiseLength = '60 mm'
        obj.addProperty('App::PropertyLength', 'MortiseDepth', 'Dimensions', 'Mortise depth').MortiseDepth = '60 mm'

        obj.addProperty('Part::PropertyPartShape', 'StockFace', 'Faces', 'Face defining stock')
        obj.addProperty('Part::PropertyPartShape', 'MortiseFace', 'Faces', 'Face defining feature')

        obj.addProperty('App::PropertyVector', 'TemporaryPosition', 'Orientation', 'Temporary mortise position').TemporaryPosition = FreeCAD.Vector(0,0,0)
        obj.addProperty('App::PropertyVector', 'TemporaryNormal', 'Orientation', 'Temporary mortise normal').TemporaryNormal = FreeCAD.Vector(0,0,1)
        obj.addProperty('App::PropertyVector', 'TemporaryDirection', 'Orientation', 'Temporary mortise direction').TemporaryDirection = FreeCAD.Vector(0,1,0)

        obj.addProperty('App::PropertyVector', 'Position', 'Orientation', 'Mortise position').Position = FreeCAD.Vector(0,0,0)
        obj.addProperty('App::PropertyVector', 'Normal', 'Orientation', 'Mortise normal').Normal = FreeCAD.Vector(0,0,1)
        obj.addProperty('App::PropertyVector', 'Direction', 'Orientation', 'Mortise direction').Direction = FreeCAD.Vector(0,1,0)

        obj.addProperty('App::PropertyBool', 'OperationExists', 'Operations', 'Linked adaptive milling operation exists').OperationExists = False

        self.execute(obj)

    def getMortiseFace(self, obj):
        "Return temporary shape created at the origin and in a default orientation"

        length = obj.MortiseLength.Value
        width = obj.MortiseWidth.Value

        ## Points in each quadrant
        point0 = FreeCAD.Vector(+width/2, +length/2-width/2, 0)
        point1 = FreeCAD.Vector(-width/2, +length/2-width/2, 0)
        point2 = FreeCAD.Vector(-width/2, -length/2+width/2, 0)
        point3 = FreeCAD.Vector(+width/2, -length/2+width/2, 0)

        line03 = Part.makeLine(point3,point0)
        line21 = Part.makeLine(point1,point2)
        
        ## Arcs
        ### Midpoints
        point10 = FreeCAD.Vector(0, +length/2, 0)
        point32 = FreeCAD.Vector(0, -length/2, 0)
        
        arc10 = Part.Edge(Part.Arc(point1,point10,point0))
        arc32 = Part.Edge(Part.Arc(point3,point32,point2))
        
        ## Face and Shape
        mortiseWire = Part.Wire([line03,arc32,line21,arc10])
        mortiseFace = Part.Face(mortiseWire)

        return mortiseFace
        
    def getStockFace(self, obj):
        "Return temporary shape created at the origin and in a default orientation"

        height = obj.StockHeight.Value
        width = obj.StockWidth.Value

        centerPoint = FreeCAD.Vector(-height/2, -width/2, 0)
        stockFace = Part.makePlane(height, width, centerPoint)

        return stockFace

    def addOperation(self, obj):
        "Create an adaptive machining operation using the Path workbench"

        document = obj.Document
        objectAdaptive = document.addObject("Path::FeaturePython", "Adaptive")
        PathAdaptive.PathAdaptive(objectAdaptive)
        objectAdaptive.Base = (obj, ['MortiseFace'])    # App::PropertyLinkSub
        objectAdaptive.Stock = (obj, ['StockFace'])  # App::PropertyLinkSub

    def execute(self, obj):
        "Executed on document recomputes"

        obj.MortiseFace = self.getMortiseFace(obj)
        obj.StockFace = self.getStockFace(obj)
        stockShape = obj.StockFace.extrude(-obj.MortiseDepth.Value * obj.TemporaryNormal)
        mortiseShape = obj.MortiseFace.extrude(-obj.MortiseDepth.Value * obj.TemporaryNormal) 
        cutoutShape = stockShape.cut(mortiseShape)

        if obj.Type == "mortise":
            obj.Shape = mortiseShape
        else:
            obj.Shape = cutoutShape

        # Placement
        obj.Placement.Base = obj.Position
        rotation1 = FreeCAD.Rotation(obj.TemporaryNormal, obj.Normal)
        rotation2 = FreeCAD.Rotation(obj.TemporaryDirection, obj.Direction)
        obj.Placement.Rotation = rotation1.multiply(rotation2)

        # Create adaptive milling operation
        if not obj.OperationExists:
            self.addOperation(obj)
            obj.OperationExists = True

def test():
    ''' 
    Create a few Mortise objects and add them to a document, for testing
    ''' 

    document = FreeCAD.ActiveDocument
    if not document: 
        document = FreeCAD.newDocument()
    
    # create some features for testing
    features = []
    
    position = FreeCAD.Vector(0,50,50)
    normal = FreeCAD.Vector(-1,0,0)
    direction = FreeCAD.Vector(0,1,0)
    type = "tenon"
    features.append((position, normal, direction, type))
    
    position = FreeCAD.Vector(200,0,50)
    normal = FreeCAD.Vector(0,-1,0)
    direction = FreeCAD.Vector(1,0,0)
    type = "mortise"
    features.append((position, normal, direction, type))
    
    position = FreeCAD.Vector(1000,50,50)
    normal = FreeCAD.Vector(1,0,0)
    direction = FreeCAD.Vector(0,1,0)
    type = "tenon"
    features.append((position, normal, direction, type))
    
    objects = []
    for (position, normal, direction, type) in features:
        objectMortise = document.addObject("Part::FeaturePython", "Mortise")
        Mortise(objectMortise)
        MortiseGui.ViewProviderBox(objectMortise.ViewObject)
        objectMortise.Position = position
        objectMortise.Normal = normal
        objectMortise.Direction = direction
        objectMortise.Type = type
        objects.append(objectMortise)
    
    # Fusion of features
    objectFusion = document.addObject("Part::MultiFuse","Features")
    objectFusion.Shapes = objects
    
    document.recompute()

