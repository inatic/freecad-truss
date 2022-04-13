import FreeCAD
import Part
import Path
import Mesh
from PathScripts import PathToolController
from Truss import BarGui
from Truss import Mortise
from Truss import PathAdaptive
from Truss import PathJob, PathJobGui
from Truss import PathStock

class Bar():
    def __init__(self, obj, mainBar, endBars, sideBars, width, height):

        obj.Proxy = self
        self.obj = obj
        doc = obj.Document

        obj.addProperty("App::PropertyString", 'Description', 'Base', 'Bar description').Description = "This is a bar"
        obj.addProperty("App::PropertyString", 'Type', 'Base', 'Object type').Type = "Bar"

        obj.addProperty("App::PropertyLength", 'Width', 'Dimensions', 'Box width').Width
        obj.addProperty("App::PropertyLength", 'Height', 'Dimensions', 'Box height').Height

        obj.addProperty("App::PropertyVector", "Test1", "Bars", "")
        obj.addProperty("App::PropertyVectorList", "Test2", "Bars", "")
        obj.addProperty("App::PropertyPythonObject", "Test3", "Bars", "")

        obj.addProperty("Part::PropertyGeometryList", "OriginalMainBar", "Bars", "Line representing the main bar.")
        obj.addProperty("Part::PropertyGeometryList", "OriginalEndBars", "Bars", "Lines representing the bars at the ends of the main bar.")
        obj.addProperty("Part::PropertyGeometryList", "OriginalSideBars", "Bars", "Lines representing the bars on the sides of the main bar.")

        obj.addProperty("Part::PropertyGeometryList", "MainBar", "Bars", "Line representing the main bar.")
        obj.addProperty("Part::PropertyGeometryList", "EndBars", "Bars", "Lines representing the bars at the ends of the main bar.")
        obj.addProperty("Part::PropertyGeometryList", "SideBars", "Bars", "Lines representing the bars on the sides of the main bar.")

        obj.addProperty("Part::PropertyPartShape", "BarLines", "Bars", "All lines representing the main bar, end bars and side bars")

        obj.Width = width
        obj.Height = height
        obj.OriginalMainBar = mainBar
        obj.OriginalEndBars = endBars
        obj.OriginalSideBars = sideBars
        obj.MainBar = mainBar
        obj.EndBars = endBars
        obj.SideBars = sideBars

        self.orientBars(obj)

        # STOCK SHAPE
        
        stockShape = self.getStockShape(obj)

        # PREPARE FEATURES

        features = []	# (position, normal, direction, type)

        ## END BARS

        mainBar = obj.MainBar[0]
        endBar0 = obj.EndBars[0]
        endBar1 = obj.EndBars[1]

        position = mainBar.StartPoint
        normal = (mainBar.StartPoint - mainBar.EndPoint).normalize()
        direction = (endBar0.EndPoint - endBar0.StartPoint).normalize()
        type = "tenon"
        features.append((position, normal, direction, type))

        position = mainBar.EndPoint
        normal = (mainBar.EndPoint - mainBar.StartPoint).normalize()
        direction = (endBar1.EndPoint - endBar1.StartPoint).normalize()
        type = "tenon"
        features.append((position, normal, direction, type))

        ## SIDE BARS

        mainBarEdge = Part.Edge(mainBar)
        stockBoundBox = stockShape.BoundBox
        for bar in obj.SideBars:
            position = stockBoundBox.getIntersectionPoint(bar.StartPoint, (bar.EndPoint-bar.StartPoint).normalize())
            normal = (bar.EndPoint - bar.StartPoint).normalize()
            direction = (mainBar.EndPoint - mainBar.StartPoint).normalize()
            type = "mortise"
            features.append((position, normal, direction, type))

        ## MORTISE OBJECTS

        mortiseObjects = []
        for (position, normal, direction, type) in features:
            mortiseObject = doc.addObject("Part::FeaturePython", "Mortise")
            mortiseResources = {
                'position': position,
                'normal': normal,
                'direction': direction,
                'type': type
            }
            Mortise.Mortise(mortiseObject, mortiseResources)
            MortiseGui.ViewProviderBox(mortiseObject.ViewObject)
            mortiseObjects.append(mortiseObject)

        ## FUSION OF FEATURES 

        objectFusion = doc.addObject("Part::MultiFuse","Features")
        objectFusion.Shapes = mortiseObjects
        if objectFusion.ViewObject:
            objectFusion.ViewObject.Visibility = False

        ## CUT MORTISE FEATURES FROM BEAM

        doc.recompute()

        featureShape = objectFusion.Shape
        beamShape = stockShape.cut(featureShape)
        obj.Shape = beamShape

        # ADAPTIVE OPERATIONS

        adaptiveObjects = []
        for mortiseObject in mortiseObjects:
            adaptiveResources = {
                'side': 'Inside' if mortiseObject.Type == 'mortise' else 'Outside',
                'liftDistance': 1,
                'clearanceHeight': 20,
                'safeHeight': 10,
                'startDepth': 0,
                'stepDown': 10,
                'finishStep': 0,
                'finalDepth': -mortiseObject.MortiseDepth.Value,
                'position': mortiseObject.Position,
                'normal': mortiseObject.Normal,
                'direction': mortiseObject.Direction
            }
            adaptiveObject = PathAdaptive.create(doc, adaptiveResources)
            adaptiveObject.Base = (mortiseObject, ['MortiseFace'])    # App::PropertyLinkSub
            adaptiveObject.Stock = (mortiseObject, ['StockFace'])     # App::PropertyLinkSub
            adaptiveObjects.append(adaptiveObject)

        # STOCK

        stockObject = doc.addObject('Part::FeaturePython', 'Stock')
        PathStock.StockFromBase(stockObject, obj, {'x':2, 'y':2, 'z':2}, {'x':2, 'y':2, 'z':2})

        # JOB

        jobObject = doc.addObject("Path::FeaturePython", "Job")
        PathJob.ObjectJob(jobObject)
        PathJobGui.ViewProvider(jobObject.ViewObject)
        jobObject.Proxy.addModels(jobObject, mortiseObjects)
        jobObject.Proxy.addStock(jobObject, stockObject)
        for adaptiveObject in adaptiveObjects:
            jobObject.Proxy.addOperation(adaptiveObject)

        # TOOL CONTROLLER

        toolController = PathToolController.Create()
        toolController.Label = 'ToolController'
        toolController.ToolNumber = 1
        toolController.VertFeed = 1000
        toolController.HorizFeed = 1000
        toolController.VertRapid = 3000
        toolController.HorizRapid = 3000
        toolController.SpindleDir = 'Forward'
        toolController.SpindleSpeed = 3500
        jobObject.Proxy.addToolController(toolController)

        # TOOL

        tool = Path.Tool()
        tool.Name = '12mm-Endmill'
        tool.ToolType = 'EndMill'
        tool.Material = 'Carbide'
        tool.Diameter = 12
        tool.CuttingEdgeHeight = 100
        tool.LengthOffset = 100
        jobObject.ToolController[0].Tool = tool

        for adaptiveObject in adaptiveObjects:
            adaptiveObject.ToolController = jobObject.ToolController[0]

    def orientBars(self, obj):
        """
        The main bar is positioned along the positive y-axis, and all other bars are transformed accordingly.
        SideBars are reversed if their StartPoint is not on the MainBar
        """

        mainBar = obj.OriginalMainBar[0]
        barWidth = obj.Width
        barHeight = obj.Height

        originalMainBarNormal = FreeCAD.Vector(0,0,1)	# still need figure this out
        originalMainBarOrientation = (mainBar.EndPoint - mainBar.StartPoint).normalize()

        targetMainBarPosition = FreeCAD.Vector(barWidth/2,0,barHeight/2)
        targetMainBarNormal = FreeCAD.Vector(0,0,1)
        targetMainBarOrientation = FreeCAD.Vector(0,1,0)
        
        placement = FreeCAD.Placement()
        placement.Base = targetMainBarPosition
        rotation1 = FreeCAD.Rotation( originalMainBarNormal, targetMainBarNormal )
        rotation2 = FreeCAD.Rotation( originalMainBarOrientation, targetMainBarOrientation )
        placement.Rotation = rotation1.multiply(rotation2)
        matrix = placement.toMatrix()

        mainBar.transform(matrix)
        obj.MainBar = mainBar

        bars = obj.OriginalEndBars
        for i, bar in enumerate(bars):
            bars[i].transform(matrix)
        obj.EndBars = bars
    
        bars = obj.OriginalSideBars
        mainBarEdge = Part.Edge(mainBar)
        for i, bar in enumerate(bars):
            bars[i].transform(matrix)

            # reverse bar if startPoint not on mainBar
            startVertex = Part.Vertex(bar.StartPoint)
            if mainBarEdge.distToShape(startVertex)[0] > 0.1:
                bars[i].reverse()

        obj.SideBars = bars

    def getStockShape(self, obj):
        """
        Get stock shape for mainBar
        """
        
        mainBar = obj.MainBar[0]
        length = mainBar.length()
        width = obj.Width
        height = obj.Height
        point = FreeCAD.Vector(0, 0, 0)
        stock = Part.makeBox(width, length, height, point)
        
        return stock

    def execute(self, obj):
        """
        Called on document recompute
        """

        pass

    def getBarEdges(self, obj):
        """
        Return edges for the main bar, side bars and end bars
        """
        edges = []

        edges.append( Part.Edge( obj.MainBar[0]) )
        for bar in obj.EndBars:
            edges.append( Part.Edge(bar) )
        for bar in obj.SideBars:
            edges.append( Part.Edge(bar) )
 
        return edges

    def drawBars(self, obj):
        """
        Draw a line for each bar
        """
        edges = self.getBarEdges(obj)
        for edge in edges:
            Part.show(edge)

def test():
    '''
    Create a simple bar, for testing
    '''

    document = FreeCAD.newDocument()
    
    # BARS

    v0 = FreeCAD.Vector( 0, 0, 0 )
    v1 = FreeCAD.Vector( 0, 1000, 0 )
    mainBar = [Part.LineSegment(v0, v1)]

    endBars = []
    v0 = FreeCAD.Vector( 300, 0, 0 )
    v1 = FreeCAD.Vector( -300, 0, 0 )
    endBars.append( Part.LineSegment(v0, v1) )
    v0 = FreeCAD.Vector( 300, 1000, 0 )
    v1 = FreeCAD.Vector( -300, 1000, 0 )
    endBars.append( Part.LineSegment(v0, v1) )

    sideBars = []
    v0 = FreeCAD.Vector( 0, 200, 0 )
    v1 = FreeCAD.Vector( 300, 200, 0 )
    sideBars.append( Part.LineSegment(v0, v1) )
    v0 = FreeCAD.Vector( 0, 400, 0 )
    v1 = FreeCAD.Vector( 0, 400, 300 )
    sideBars.append( Part.LineSegment(v0, v1) )
    v0 = FreeCAD.Vector( 0, 600, 0 )
    v1 = FreeCAD.Vector( 0, 600, 300 )
    sideBars.append( Part.LineSegment(v0, v1) )
    v0 = FreeCAD.Vector( 0, 800, 0 )
    v1 = FreeCAD.Vector( 0, 800, 300 )
    sideBars.append( Part.LineSegment(v0, v1) )
    
    # BAR OBJECT

    barObject = document.addObject("Part::FeaturePython", "TestBar")
    width = 100
    height = 100
    Bar(barObject, mainBar, endBars, sideBars, width, height)
    BarGui.ViewProviderBox(barObject.ViewObject)
    
    document.recompute()

    return barObject
